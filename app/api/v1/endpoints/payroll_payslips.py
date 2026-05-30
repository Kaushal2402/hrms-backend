import uuid
import os
from typing import List, Optional, Union
from datetime import date
from fastapi import APIRouter, Depends, HTTPException, Query, status, BackgroundTasks
from fastapi.responses import FileResponse
import csv
from openpyxl import Workbook
from sqlalchemy.orm import Session
from sqlalchemy import func, or_, and_

from app.api import deps
from app.db.session import SessionLocal
from app.models.organization import Organization
from app.models.employee import Employee, Department
from app.models.payroll import Payslip, PayrollStatus, PayrollPeriod, PayslipStatus
from app.schemas.payroll_payslips import (
    PayslipSchema, PayslipListResponse, PayslipResponse, 
    PayslipHoldUpdate, PayslipReverseCreate, BulkEmailRequest
)
from app.core.permissions import PayrollPayslipPermissions
from app.utils.email import send_payslip_email
from app.utils.pdf import generate_pdf, get_payslip_html
from app.utils.payroll_audit import PayrollAuditService
from datetime import datetime

router = APIRouter()
employee_router = APIRouter()

def _get_org_id(current_user: Union[Organization, Employee]) -> int:
    return current_user.id if isinstance(current_user, Organization) else current_user.organization_id

def _require_permission(db: Session, current_user: Union[Organization, Employee], code: str, action_label: str):
    if not isinstance(current_user, Organization) and not deps.has_permission(db, current_user, code):
        raise HTTPException(status_code=403, detail=f"You do not have permission to {action_label}")

@router.get("/", response_model=PayslipListResponse)
def get_payslips(
    period_uuid: Optional[uuid.UUID] = Query(None, alias="period_id"),
    employee_uuid: Optional[uuid.UUID] = Query(None, alias="employee_id"),
    department_uuid: Optional[uuid.UUID] = Query(None, alias="department_id"),
    status: Optional[str] = None,
    from_date: Optional[date] = None,
    to_date: Optional[date] = None,
    is_published: Optional[bool] = None,
    is_reversed: Optional[bool] = None,
    is_on_hold: Optional[bool] = None,
    page: int = Query(1, ge=1),
    limit: int = Query(10, ge=1, le=100),
    search: Optional[str] = None,
    sort_by: Optional[str] = Query("created_at"),
    sort_order: Optional[str] = Query("desc"),
    db: Session = Depends(deps.get_db),
    current_user: Union[Organization, Employee] = Depends(deps.get_current_user)
):
    _require_permission(db, current_user, PayrollPayslipPermissions.READ, "list payslips")
    org_id = _get_org_id(current_user)
    
    query = db.query(Payslip, Employee, Department, PayrollPeriod)\
        .join(Employee, Payslip.employee_id == Employee.id)\
        .outerjoin(Department, Employee.department_id == Department.id)\
        .join(PayrollPeriod, Payslip.payroll_period_id == PayrollPeriod.id)\
        .filter(Payslip.organization_id == org_id)
    
    # If the user is an employee, only restrict to their own payslips if they do not have the READ permission.
    # Note: the _require_permission check above ensures they have READ permission to even list at all,
    # but let's be safe and check if they have READ permission before showing all.
    if not isinstance(current_user, Organization) and not deps.has_permission(db, current_user, PayrollPayslipPermissions.READ):
        query = query.filter(Payslip.employee_id == current_user.id)
    
    if period_uuid: 
        query = query.filter(PayrollPeriod.uuid == period_uuid)
    
    if employee_uuid: 
        query = query.filter(Employee.uuid == employee_uuid)
    
    if department_uuid:
        query = query.filter(Department.uuid == department_uuid)
        
    if search:
        query = query.filter(or_(
            Payslip.payslip_number.ilike(f"%{search}%"),
            Employee.first_name.ilike(f"%{search}%"),
            Employee.last_name.ilike(f"%{search}%"),
            Employee.employee_code.ilike(f"%{search}%")
        ))

    if status: query = query.filter(Payslip.status == status)
    if is_published is not None: query = query.filter(Payslip.is_published == is_published)
    if is_reversed is not None: query = query.filter(Payslip.is_reversed == is_reversed)
    if is_on_hold is not None: query = query.filter(Payslip.is_on_hold == is_on_hold)
    if from_date: query = query.filter(Payslip.period_start_date >= from_date)
    if to_date: query = query.filter(Payslip.period_end_date <= to_date)

    allowed_sort = ["created_at", "payslip_number", "net_salary"]
    if sort_by not in allowed_sort: sort_by = "created_at"
    
    sort_attr = getattr(Payslip, sort_by)
    if sort_order == "desc":
        query = query.order_by(sort_attr.desc())
    else:
        query = query.order_by(sort_attr.asc())

    total_records = query.count()
    items = query.offset((page - 1) * limit).limit(limit).all()
    
    results = []
    for payslip, emp, dept, period in items:
        p_schema = PayslipSchema.model_validate(payslip)
        p_schema.employee_name = f"{emp.first_name} {emp.last_name}"
        p_schema.employee_code = emp.employee_code
        p_schema.department_name = dept.department_name if dept else None
        p_schema.period_name = period.period_name
        results.append(p_schema)
    return PayslipListResponse(
        success=True, message="Payslips retrieved successfully",
        data=results,
        pagination={"total_records": total_records, "current_page": page, "total_pages": (total_records + limit - 1) // limit, "page_size": limit}
    )

@router.get("/export")
def export_payslips(
    period_id: Optional[str] = Query(None),
    employee_id: Optional[str] = Query(None),
    department_id: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    format: str = Query("csv", regex="^(csv|excel)$"),
    db: Session = Depends(deps.get_db),
    current_user: Union[Organization, Employee] = Depends(deps.get_current_user)
):
    _require_permission(db, current_user, PayrollPayslipPermissions.READ, "export payslips")
    org_id = _get_org_id(current_user)
    
    # Real Data Generation Logic
    query = db.query(Payslip, Employee, PayrollPeriod)\
        .join(Employee, Payslip.employee_id == Employee.id)\
        .join(PayrollPeriod, Payslip.payroll_period_id == PayrollPeriod.id)\
        .filter(Payslip.organization_id == org_id)
        
    if period_id: query = query.filter(PayrollPeriod.uuid == period_id)
    if employee_id: query = query.filter(Employee.uuid == employee_id)
    if status: query = query.filter(Payslip.status == status)
    
    items = query.all()
    
    # Correct path to root/mock_files/exports
    mock_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "..", "..", "mock_files", "exports")
    os.makedirs(mock_dir, exist_ok=True)
    file_path = os.path.join(mock_dir, f"payslips_{org_id}.{format}")
    
    # Prepare Headers
    headers = [
        "Payslip No", "Employee Name", "Employee Code", "Period", 
        "Basic Salary", "Total Earnings", "Total Deductions", "Net Salary", "Status"
    ]
    
    rows = []
    for payslip, emp, period in items:
        rows.append([
            payslip.payslip_number,
            f"{emp.first_name} {emp.last_name}",
            emp.employee_code,
            period.period_name,
            float(payslip.basic_salary or 0),
            float(payslip.total_earnings or 0),
            float(payslip.total_deductions or 0),
            float(payslip.net_salary or 0),
            payslip.status
        ])

    # Generate File
    if format == "csv":
        with open(file_path, "w", newline='') as f:
            writer = csv.writer(f)
            writer.writerow(headers)
            writer.writerows(rows)
    else:
        wb = Workbook()
        ws = wb.active
        ws.title = "Payslips Export"
        ws.append(headers)
        for row in rows:
            ws.append(row)
        wb.save(file_path)

    return FileResponse(
        path=file_path,
        filename=f"payslips_export_{datetime.now().strftime('%Y%m%d')}.{format if format != 'excel' else 'xlsx'}",
        media_type='application/octet-stream'
    )

@router.get("/{payslip_uuid}", response_model=PayslipResponse)
def get_payslip_details(payslip_uuid: uuid.UUID, db: Session = Depends(deps.get_db), current_user: Union[Organization, Employee] = Depends(deps.get_current_user)):
    org_id = _get_org_id(current_user)
    result = db.query(Payslip, Employee, Department, PayrollPeriod)\
        .join(Employee, Payslip.employee_id == Employee.id)\
        .outerjoin(Department, Employee.department_id == Department.id)\
        .join(PayrollPeriod, Payslip.payroll_period_id == PayrollPeriod.id)\
        .filter(Payslip.uuid == payslip_uuid, Payslip.organization_id == org_id).first()
        
    if not result: raise HTTPException(status_code=404, detail="Payslip not found")
    
    payslip, emp, dept, period = result
    if not isinstance(current_user, Organization) and payslip.employee_id != current_user.id:
        if not deps.has_permission(db, current_user, PayrollPayslipPermissions.READ):
            raise HTTPException(status_code=403, detail="Access denied")

    p_schema = PayslipSchema.model_validate(payslip)
    p_schema.employee_name = f"{emp.first_name} {emp.last_name}"
    p_schema.employee_code = emp.employee_code
    p_schema.department_name = dept.department_name if dept else None
    p_schema.period_name = period.period_name
    
    return {"success": True, "message": "Payslip retrieved successfully", "data": p_schema}

@router.patch("/{payslip_uuid}/hold", response_model=PayslipResponse)
def hold_payslip(payslip_uuid: uuid.UUID, data: PayslipHoldUpdate, db: Session = Depends(deps.get_db), current_user: Union[Organization, Employee] = Depends(deps.get_current_user)):
    _require_permission(db, current_user, PayrollPayslipPermissions.PUBLISH, "hold payslip")
    item = db.query(Payslip).filter(Payslip.uuid == payslip_uuid, Payslip.organization_id == _get_org_id(current_user)).first()
    if not item: raise HTTPException(404, "Payslip not found")
    if item.is_reversed:
        raise HTTPException(400, "Cannot hold a reversed payslip")
    
    before_state = PayrollAuditService.get_model_dict(item)
    
    item.is_on_hold = True
    item.hold_reason = data.hold_reason
    
    db.commit()
    db.refresh(item)
    
    PayrollAuditService.log(
        db=db,
        current_user=current_user,
        action_type="payslip_held",
        entity_type="payslip",
        entity_id=item.id,
        employee_id=item.employee_id,
        before_state=before_state,
        after_state=PayrollAuditService.get_model_dict(item),
        risk_level="high",
        change_summary=f"Held payslip for {item.employee.first_name}"
    )
    
    return {"success": True, "message": "Payslip placed on hold", "data": item}

@router.post("/{payslip_uuid}/reverse", response_model=PayslipResponse)
def reverse_payslip(payslip_uuid: uuid.UUID, data: PayslipReverseCreate, db: Session = Depends(deps.get_db), current_user: Union[Organization, Employee] = Depends(deps.get_current_user)):
    _require_permission(db, current_user, PayrollPayslipPermissions.REVERSE, "reverse payslip")
    item = db.query(Payslip).filter(Payslip.uuid == payslip_uuid, Payslip.organization_id == _get_org_id(current_user)).first()
    if not item: raise HTTPException(404, "Payslip not found")
    if item.is_reversed:
        raise HTTPException(400, "Payslip is already reversed")
        
    before_state = PayrollAuditService.get_model_dict(item)
    
    item.is_reversed = True
    item.reversal_reason = data.reversal_reason
    
    db.commit()
    db.refresh(item)
    
    PayrollAuditService.log(
        db=db,
        current_user=current_user,
        action_type="payslip_reversed",
        entity_type="payslip",
        entity_id=item.id,
        employee_id=item.employee_id,
        before_state=before_state,
        after_state=PayrollAuditService.get_model_dict(item),
        risk_level="high",
        change_summary=f"Reversed payslip for {item.employee.first_name}"
    )
    
    return {"success": True, "message": "Payslip reversed successfully", "data": item}

def process_bulk_email(payslip_ids: List[int]):
    db = SessionLocal()
    try:
        # Re-fetch with needed relationships
        items = db.query(Payslip, Employee, PayrollPeriod)\
            .join(Employee, Payslip.employee_id == Employee.id)\
            .join(PayrollPeriod, Payslip.payroll_period_id == PayrollPeriod.id)\
            .filter(Payslip.id.in_(payslip_ids)).all()
            
        for payslip, emp, period in items:
            try:
                send_payslip_email(
                    email_to=emp.work_email,
                    employee_name=f"{emp.first_name} {emp.last_name}",
                    period_name=period.period_name,
                    net_salary=float(payslip.net_salary),
                    payslip_number=payslip.payslip_number
                )
                payslip.email_sent = True
                payslip.email_sent_at = datetime.utcnow()
            except Exception as inner_e:
                print(f"Failed to send individual payslip email to {emp.work_email}: {inner_e}")
                
        db.commit()
    except Exception as e:
        print(f"Error in process_bulk_email background task: {e}")
    finally:
        db.close()

@router.post("/bulk-email", response_model=dict)
def bulk_email_payslips(
    data: BulkEmailRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(deps.get_db),
    current_user: Union[Organization, Employee] = Depends(deps.get_current_user)
):
    _require_permission(db, current_user, PayrollPayslipPermissions.PUBLISH, "send bulk emails")
    org_id = _get_org_id(current_user)
    
    # Verify payslips exist and belong to org
    payslips = db.query(Payslip.id).filter(
        Payslip.uuid.in_(data.payslip_uuids),
        Payslip.organization_id == org_id
    ).all()
    
    if not payslips:
        raise HTTPException(status_code=404, detail="No valid payslips found for email")
    
    payslip_ids = [p.id for p in payslips]
    
    # Enqueue background task
    background_tasks.add_task(process_bulk_email, payslip_ids)
    
    return {
        "success": True,
        "message": f"Emails queued for {len(payslip_ids)} payslips",
        "data": {"count": len(payslip_ids)}
    }

@router.post("/{payslip_uuid}/send-email", response_model=dict)
def send_single_payslip_email(
    payslip_uuid: uuid.UUID,
    db: Session = Depends(deps.get_db),
    current_user: Union[Organization, Employee] = Depends(deps.get_current_user)
):
    _require_permission(db, current_user, PayrollPayslipPermissions.PUBLISH, "send email")
    org_id = _get_org_id(current_user)
    
    result = db.query(Payslip, Employee, PayrollPeriod)\
        .join(Employee, Payslip.employee_id == Employee.id)\
        .join(PayrollPeriod, Payslip.payroll_period_id == PayrollPeriod.id)\
        .filter(Payslip.uuid == payslip_uuid, Payslip.organization_id == org_id).first()
    
    if not result:
        raise HTTPException(status_code=404, detail="Payslip not found")
    
    payslip, emp, period = result
    
    try:
        send_payslip_email(
            email_to=emp.work_email,
            employee_name=f"{emp.first_name} {emp.last_name}",
            period_name=period.period_name,
            net_salary=float(payslip.net_salary),
            payslip_number=payslip.payslip_number
        )
        payslip.email_sent = True
        payslip.email_sent_at = datetime.utcnow()
        db.commit()
    except Exception as e:
        print(f"Failed to send individual payslip email: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to send email: {str(e)}")
    
    return {"success": True, "message": "Email sent successfully", "data": None}
@router.get("/{payslip_uuid}/download")
def download_payslip(
    payslip_uuid: uuid.UUID,
    db: Session = Depends(deps.get_db),
    current_user: Union[Organization, Employee] = Depends(deps.get_current_user)
):
    org_id = _get_org_id(current_user)
    
    # Fetch with relationships for the PDF template
    result = db.query(Payslip, Employee, PayrollPeriod, Organization)\
        .join(Employee, Payslip.employee_id == Employee.id)\
        .join(PayrollPeriod, Payslip.payroll_period_id == PayrollPeriod.id)\
        .join(Organization, Payslip.organization_id == Organization.id)\
        .filter(Payslip.uuid == payslip_uuid, Payslip.organization_id == org_id).first()
    
    if not result:
        raise HTTPException(status_code=404, detail="Payslip not found")
        
    payslip, emp, period, org = result
    
    if not isinstance(current_user, Organization) and payslip.employee_id != current_user.id:
        if not deps.has_permission(db, current_user, PayrollPayslipPermissions.READ):
            raise HTTPException(status_code=403, detail="Not authorized to download this payslip")

    # Real PDF Generation Logic
    # Correct path to root/mock_files/payslips
    base_dir = os.path.dirname(os.path.abspath(__file__))
    mock_dir = os.path.join(base_dir, "..", "..", "..", "..", "mock_files", "payslips")
    os.makedirs(mock_dir, exist_ok=True)
    file_path = os.path.join(mock_dir, f"{payslip.uuid}.pdf")
    
    # Prepare data for template
    pdf_data = {
        "organization_name": org.name,
        "employee_name": f"{emp.first_name} {emp.last_name}",
        "employee_code": emp.employee_code,
        "department_name": "N/A",
        "designation": "Employee",
        "payslip_number": payslip.payslip_number,
        "period_name": period.period_name,
        "payment_date": payslip.payment_date.strftime("%Y-%m-%d") if payslip.payment_date else "N/A",
        "basic_salary": float(payslip.basic_salary or 0),
        "gross_salary": float(payslip.gross_salary or 0),
        "total_earnings": float(payslip.total_earnings or 0),
        "total_deductions": float(payslip.total_deductions or 0),
        "tax_deducted": float(payslip.tax_deducted or 0),
        "lop_amount": float(payslip.lop_amount or 0),
        "net_salary": float(payslip.net_salary or 0)
    }
    
    html = get_payslip_html(pdf_data)
    pdf_content = generate_pdf(html)
    
    if pdf_content:
        with open(file_path, "wb") as f:
            f.write(pdf_content.getvalue())
    else:
        raise HTTPException(status_code=500, detail="Failed to generate PDF content")
            
    return FileResponse(
        path=file_path,
        filename=f"payslip_{payslip.payslip_number}.pdf",
        media_type='application/pdf'
    )

@router.post("/{payslip_uuid}/regenerate", response_model=dict)
def regenerate_payslip(
    payslip_uuid: uuid.UUID,
    db: Session = Depends(deps.get_db),
    current_user: Union[Organization, Employee] = Depends(deps.get_current_user)
):
    _require_permission(db, current_user, PayrollPayslipPermissions.PUBLISH, "regenerate payslip")
    org_id = _get_org_id(current_user)
    payslip = db.query(Payslip).filter(Payslip.uuid == payslip_uuid, Payslip.organization_id == org_id).first()
    
    if not payslip:
        raise HTTPException(status_code=404, detail="Payslip not found")
    
    if payslip.is_published:
        raise HTTPException(status_code=400, detail="Cannot regenerate a published payslip. Reverse it first.")

    before_state = PayrollAuditService.get_model_dict(payslip)
    
    payslip.updated_at = func.now()
    db.commit()
    db.refresh(payslip)
    
    PayrollAuditService.log(
        db=db,
        current_user=current_user,
        action_type="payslip_regenerated",
        entity_type="payslip",
        entity_id=payslip.id,
        employee_id=payslip.employee_id,
        before_state=before_state,
        after_state=PayrollAuditService.get_model_dict(payslip),
        risk_level="high",
        change_summary=f"Regenerated payslip for {payslip.employee.first_name}"
    )
    
    return {"success": True, "message": "Payslip regeneration triggered", "data": None}


# Employee-specific routes (will be registered under /payroll/employees)
@employee_router.get("/me/payslips", response_model=PayslipListResponse)
def get_my_payslips(
    page: int = Query(1, ge=1),
    limit: int = Query(10, ge=1, le=100),
    sort_by: str = Query("created_at"),
    sort_order: str = Query("desc"),
    period_id: Optional[str] = Query(None),
    db: Session = Depends(deps.get_db),
    current_user: Employee = Depends(deps.get_current_user)
):
    if isinstance(current_user, Organization):
        raise HTTPException(status_code=400, detail="Organizations do not have personal payslips")
        
    query = db.query(Payslip, PayrollPeriod)\
        .join(PayrollPeriod, Payslip.payroll_period_id == PayrollPeriod.id)\
        .filter(Payslip.employee_id == current_user.id)
        
    if period_id:
        query = query.filter(PayrollPeriod.uuid == period_id)
        
    allowed_sort = ["created_at", "payslip_number", "net_salary", "period_start_date"]
    if sort_by not in allowed_sort: sort_by = "created_at"
    
    sort_attr = getattr(Payslip, sort_by)
    if sort_order == "desc":
        query = query.order_by(sort_attr.desc())
    else:
        query = query.order_by(sort_attr.asc())
        
    total_records = query.count()
    items = query.offset((page - 1) * limit).limit(limit).all()
    
    results = []
    for payslip, period in items:
        p_schema = PayslipSchema.model_validate(payslip)
        p_schema.period_name = period.period_name
        p_schema.employee_name = f"{current_user.first_name} {current_user.last_name}"
        results.append(p_schema)
    
    return PayslipListResponse(
        success=True, 
        message="My payslips retrieved successfully",
        data=results,
        pagination={"total_records": total_records, "current_page": page, "total_pages": max(1, (total_records + limit - 1) // limit), "page_size": limit}
    )

@employee_router.get("/{employee_uuid}/payslips", response_model=PayslipListResponse)
def get_employee_payslips(
    employee_uuid: uuid.UUID,
    db: Session = Depends(deps.get_db),
    current_user: Union[Organization, Employee] = Depends(deps.get_current_user)
):
    _require_permission(db, current_user, PayrollPayslipPermissions.READ, "view employee payslips")
    org_id = _get_org_id(current_user)
    
    target_employee = db.query(Employee).filter(Employee.uuid == employee_uuid, Employee.organization_id == org_id).first()
    if not target_employee:
        raise HTTPException(status_code=404, detail="Employee not found")
        
    payslips = db.query(Payslip).filter(
        Payslip.employee_id == target_employee.id,
        Payslip.organization_id == org_id
    ).order_by(Payslip.period_start_date.desc()).all()
    
    return PayslipListResponse(
        success=True, 
        message=f"Payslips for {target_employee.first_name} retrieved successfully",
        data=[PayslipSchema.model_validate(p) for p in payslips],
        pagination={"total_records": len(payslips), "current_page": 1, "total_pages": 1, "page_size": len(payslips)}
    )
