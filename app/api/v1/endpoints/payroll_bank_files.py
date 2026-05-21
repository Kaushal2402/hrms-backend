import uuid
import csv
import io
import logging
from decimal import Decimal
from datetime import datetime, date
from typing import List, Optional, Union, Literal
from fastapi import APIRouter, Depends, HTTPException, Query, status, BackgroundTasks
from fastapi.responses import StreamingResponse
from pathlib import Path
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import func, or_
from app.api import deps
from app.core.config import settings
from app.db.session import SessionLocal
from app.models.organization import Organization
from app.models.employee import Employee
from app.models.payroll import BankFile, BankFileRecord, PayrollPeriod, PayrollStatus, Payslip
from app.schemas.payroll_bank_files import (
    BankFileSchema, BankFileListResponse, BankFileResponse, 
    BankFileCreate, BankConfirmationUpdate, BankFileRecordListResponse
)
from app.core.permissions import PayrollBankFilePermissions
from app.utils.upload import get_file_url

logger = logging.getLogger(__name__)
router = APIRouter()



def _get_org_id(current_user: Union[Organization, Employee]) -> int:
    return current_user.id if isinstance(current_user, Organization) else current_user.organization_id

def _require_permission(db, current_user, code, action_label):
    if isinstance(current_user, Organization): return
    if not deps.has_permission(db, current_user, code):
        raise HTTPException(status_code=403, detail=f"Permission denied: {action_label}")

def process_bank_file_generation_task(bank_file_id: int, period_id: int):
    db = SessionLocal()
    try:
        payslips = db.query(Payslip).options(
            joinedload(Payslip.employee).joinedload(Employee.bank_accounts),
            joinedload(Payslip.bank_account)
        ).filter(Payslip.payroll_period_id == period_id).all()

        records = []
        for p in payslips:
            # Prefer bank account linked directly to the payslip
            bank_acct = p.bank_account

            # Fall back to employee's primary bank account
            if bank_acct is None and p.employee and p.employee.bank_accounts:
                primary = next(
                    (ba for ba in p.employee.bank_accounts if ba.is_primary and ba.is_active),
                    None
                )
                if primary is None:
                    # Take any active account
                    primary = next(
                        (ba for ba in p.employee.bank_accounts if ba.is_active),
                        None
                    )
                bank_acct = primary

            record = BankFileRecord(
                bank_file_id=bank_file_id,
                payslip_id=p.id,
                employee_id=p.employee_id,
                employee_name=p.employee.full_name if p.employee else "Unknown",
                bank_account_number=bank_acct.account_number if bank_acct else "N/A",
                ifsc_code=bank_acct.ifsc_code if bank_acct else None,
                bank_name=bank_acct.bank_name if bank_acct else None,
                net_salary=p.net_salary
            )
            db.add(record)
            records.append(record)

        bank_file = db.query(BankFile).filter(BankFile.id == bank_file_id).first()
        file_path = None
        if bank_file:
            upload_base = Path(settings.UPLOAD_DIR)
            target_dir = upload_base / "bank_files"
            target_dir.mkdir(parents=True, exist_ok=True)
            file_path = target_dir / f"{bank_file.file_number}.csv"

            with open(file_path, "w", newline="") as f:
                writer = csv.writer(f)
                writer.writerow(["Employee Name", "Bank Account Number", "IFSC Code", "Bank Name", "Net Salary", "Payment Status"])
                for r in records:
                    writer.writerow([
                        r.employee_name,
                        r.bank_account_number,
                        r.ifsc_code or "",
                        r.bank_name or "",
                        str(r.net_salary),
                        "pending"
                    ])

            bank_file.status = "generated"
        db.commit()
    except Exception as e:
        db.rollback()
        if file_path and file_path.exists():
            try:
                file_path.unlink()
            except Exception:
                pass
        logger.error(f"Error in process_bank_file_generation_task: {e}", exc_info=True)
        db_err = SessionLocal()
        try:
            bank_file = db_err.query(BankFile).filter(BankFile.id == bank_file_id).first()
            if bank_file:
                bank_file.status = "failed"
                db_err.commit()
        except Exception as inner_e:
            logger.error(f"Failed to update status to failed: {inner_e}", exc_info=True)
        finally:
            db_err.close()
    finally:
        db.close()

@router.get("/", response_model=BankFileListResponse)
def get_bank_files(
    page: int = Query(1, ge=1),
    limit: int = Query(10, ge=1, le=100),
    period_uuid: Optional[uuid.UUID] = None,
    status: Optional[str] = None,
    sort_by: Optional[Literal["generated_at", "file_number", "total_records", "total_amount", "status"]] = Query("generated_at", description="Field to sort by"),
    order: Optional[Literal["asc", "desc"]] = Query("desc", description="Sort order (asc/desc)"),
    search: Optional[str] = Query(None, description="Search term for file number or name"),
    db: Session = Depends(deps.get_db),
    current_user: Union[Organization, Employee] = Depends(deps.get_current_user)
):
    _require_permission(db, current_user, PayrollBankFilePermissions.READ, "list bank files")
    org_id = _get_org_id(current_user)
    query = db.query(BankFile).filter(BankFile.organization_id == org_id)
    
    if period_uuid:
        query = query.join(PayrollPeriod).filter(PayrollPeriod.uuid == period_uuid)
    if status:
        query = query.filter(BankFile.status == status)
    if search:
        query = query.filter(
            or_(
                BankFile.file_number.ilike(f"%{search}%"),
                BankFile.file_name.ilike(f"%{search}%")
            )
        )
        
    allowed_sort_map = {
        "generated_at": BankFile.generated_at,
        "file_number": BankFile.file_number,
        "total_records": BankFile.total_records,
        "total_amount": BankFile.total_amount,
        "status": BankFile.status
    }
    if sort_by not in allowed_sort_map:
        sort_by = "generated_at"
    sort_column = allowed_sort_map[sort_by]
    query = query.order_by(sort_column.desc() if order == "desc" else sort_column.asc())
        
    total_records = query.count()
    items = query.offset((page - 1) * limit).limit(limit).all()
    return BankFileListResponse(
        success=True, message="Bank files retrieved successfully", data=items,
        pagination={"total_records": total_records, "current_page": page, "total_pages": (total_records + limit - 1) // limit, "page_size": limit}
    )

@router.post("/generate", response_model=BankFileResponse)
def generate_bank_file(
    item_in: BankFileCreate,
    background_tasks: BackgroundTasks,
    db: Session = Depends(deps.get_db),
    current_user: Union[Organization, Employee] = Depends(deps.get_current_user)
):
    _require_permission(db, current_user, PayrollBankFilePermissions.CREATE, "generate bank file")
    org_id = _get_org_id(current_user)
    
    period = db.query(PayrollPeriod).filter(PayrollPeriod.uuid == item_in.period_uuid, PayrollPeriod.organization_id == org_id).first()
    if not period or period.status not in [PayrollStatus.APPROVED, PayrollStatus.PROCESSED]:
        raise HTTPException(400, "Period must be approved or processed")
        
    payslips_summary = db.query(
        func.count(Payslip.id),
        func.sum(Payslip.net_salary)
    ).filter(Payslip.payroll_period_id == period.id).first()
    
    total_records = payslips_summary[0] or 0
    total_amount = payslips_summary[1] or Decimal('0.00')
    
    file_number = f"BF-{period.period_code}-{uuid.uuid4().hex[:8].upper()}"
    bank_file = BankFile(
        organization_id=org_id, payroll_period_id=period.id, file_number=file_number,
        file_name=f"BankFile_{file_number}.csv", file_format=item_in.bank_format,
        total_records=total_records, total_amount=total_amount,
        file_url=get_file_url(f"bank_files/{file_number}.csv"), generated_by=current_user.id,
        status="generating"
    )
    
    db.add(bank_file)
    db.commit()
    db.refresh(bank_file)
    
    background_tasks.add_task(process_bank_file_generation_task, bank_file.id, period.id)
    
    return BankFileResponse(success=True, message="Bank file generation queued successfully", data=bank_file)

@router.get("/{file_uuid}", response_model=BankFileResponse)
def get_bank_file(file_uuid: uuid.UUID, db: Session = Depends(deps.get_db), current_user: Union[Organization, Employee] = Depends(deps.get_current_user)):
    _require_permission(db, current_user, PayrollBankFilePermissions.READ, "view bank file")
    file = db.query(BankFile).filter(BankFile.uuid == file_uuid, BankFile.organization_id == _get_org_id(current_user)).first()
    if not file: raise HTTPException(404, "Bank file not found")
    return BankFileResponse(success=True, message="Bank file retrieved successfully", data=file)

@router.get("/{file_uuid}/records", response_model=BankFileRecordListResponse)
def get_bank_file_records(
    file_uuid: uuid.UUID,
    payment_status: Optional[str] = None,
    page: int = Query(1, ge=1),
    limit: int = Query(10, ge=1, le=100),
    db: Session = Depends(deps.get_db),
    current_user: Union[Organization, Employee] = Depends(deps.get_current_user)
):
    _require_permission(db, current_user, PayrollBankFilePermissions.READ, "view records")
    file = db.query(BankFile).filter(
        BankFile.uuid == file_uuid,
        BankFile.organization_id == _get_org_id(current_user)
    ).first()
    if not file:
        raise HTTPException(404, "Bank file not found")

    base_query = db.query(BankFileRecord, Employee.uuid.label("emp_uuid")).join(
        Employee, BankFileRecord.employee_id == Employee.id
    ).filter(BankFileRecord.bank_file_id == file.id)

    if payment_status:
        base_query = base_query.filter(BankFileRecord.payment_status == payment_status)

    total_records = base_query.count()
    rows = base_query.offset((page - 1) * limit).limit(limit).all()

    # Attach employee_uuid to each record object before serialisation
    items = []
    for record, emp_uuid in rows:
        record.employee_uuid = str(emp_uuid) if emp_uuid else None
        items.append(record)

    return BankFileRecordListResponse(
        success=True,
        message="Records retrieved successfully",
        data=items,
        pagination={
            "total_records": total_records,
            "current_page": page,
            "total_pages": (total_records + limit - 1) // limit,
            "page_size": limit
        }
    )

@router.get("/{file_uuid}/download")
def download_bank_file(
    file_uuid: uuid.UUID,
    db: Session = Depends(deps.get_db),
    current_user: Union[Organization, Employee] = Depends(deps.get_current_user)
):
    _require_permission(db, current_user, PayrollBankFilePermissions.READ, "download bank file")
    file = db.query(BankFile).filter(BankFile.uuid == file_uuid, BankFile.organization_id == _get_org_id(current_user)).first()
    if not file:
        raise HTTPException(404, "Bank file not found")
        
    import tempfile
    temp_file = tempfile.NamedTemporaryFile(mode="w+", newline="", delete=False)
    try:
        writer = csv.writer(temp_file)
        writer.writerow(["Employee Name", "Bank Account Number", "IFSC Code", "Bank Name", "Net Salary", "Payment Status", "UTR Number", "Payment Date"])
        
        query = db.query(BankFileRecord).filter(BankFileRecord.bank_file_id == file.id)
        for record in query.yield_per(100):
            writer.writerow([
                record.employee_name,
                record.bank_account_number,
                record.ifsc_code or "",
                record.bank_name or "",
                str(record.net_salary),
                record.payment_status,
                record.utr_number or "",
                record.payment_date.strftime("%Y-%m-%d") if record.payment_date else ""
            ])
        temp_file.flush()
        temp_file.seek(0)
        
        def iter_file():
            with open(temp_file.name, "rb") as f:
                while chunk := f.read(65536):
                    yield chunk
            try:
                Path(temp_file.name).unlink()
            except Exception:
                pass
                
        response = StreamingResponse(iter_file(), media_type="text/csv")
        response.headers["Content-Disposition"] = f"attachment; filename={file.file_name}"
        return response
    except Exception as e:
        try:
            Path(temp_file.name).unlink()
        except Exception:
            pass
        raise e

@router.post("/{file_uuid}/upload-confirmation")
def upload_confirmation(
    file_uuid: uuid.UUID,
    data: BankConfirmationUpdate,
    db: Session = Depends(deps.get_db),
    current_user: Union[Organization, Employee] = Depends(deps.get_current_user)
):
    _require_permission(db, current_user, PayrollBankFilePermissions.UPDATE, "upload confirmation")
    file = db.query(BankFile).filter(BankFile.uuid == file_uuid, BankFile.organization_id == _get_org_id(current_user)).first()
    if not file:
        raise HTTPException(404, "Bank file not found")
        
    if file.status != "generated":
        raise HTTPException(400, "Confirmation can only be uploaded for generated bank files")
        
    utr_dict = {}
    if data.utr_numbers:
        utr_dict = {item.employee_uuid: item.utr_number for item in data.utr_numbers if item.utr_number}
        
    file.bank_confirmation_received = True
    file.bank_utr_numbers = utr_dict
    file.status = "processed"
    
    if utr_dict:
        utr_list = list(utr_dict.values())
        if len(utr_list) != len(set(utr_list)):
            raise HTTPException(400, "Duplicate UTR numbers in request payload")
            
        existing_utrs = db.query(BankFileRecord.utr_number)\
            .filter(
                BankFileRecord.utr_number.in_(utr_list),
                BankFileRecord.bank_file_id != file.id
            ).all()
        if existing_utrs:
            duplicate_utrs = [u[0] for u in existing_utrs]
            raise HTTPException(400, f"Duplicate UTR numbers detected in system: {', '.join(duplicate_utrs)}")
            
        records_with_uuid = db.query(BankFileRecord, Employee.uuid)\
            .join(Employee, BankFileRecord.employee_id == Employee.id)\
            .filter(
                BankFileRecord.bank_file_id == file.id,
                Employee.organization_id == _get_org_id(current_user),
                Employee.uuid.in_(list(utr_dict.keys()))
            ).all()
            
        for record, emp_uuid in records_with_uuid:
            record.utr_number = utr_dict[emp_uuid]
            record.payment_status = "paid"
            record.payment_date = date.today()
                
    db.commit()
    return {"success": True, "message": "Confirmation uploaded successfully"}