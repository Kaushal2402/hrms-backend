import uuid
import os
from typing import List, Optional, Union
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from sqlalchemy import func, or_
from app.api import deps
from app.models.organization import Organization
from app.models.employee import Employee
from app.models.payroll import FinalSettlement
from app.schemas.payroll_final_settlements import (
    FinalSettlementCreate, FinalSettlementUpdate, FinalSettlementSchema,
    FinalSettlementListResponse, FinalSettlementResponse, SettlementApprovalUpdate,
    SettlementPaymentUpdate
)
from app.utils.pdf import generate_pdf, get_final_settlement_html

router = APIRouter()

def _get_org_id(current_user: Union[Organization, Employee]) -> int:
    return current_user.id if isinstance(current_user, Organization) else current_user.organization_id

def _require_permission(db, current_user, code, action_label):
    if isinstance(current_user, Organization): return
    if not deps.has_permission(db, current_user, code):
        raise HTTPException(status_code=403, detail=f"Permission denied for {action_label}")

def calculate_settlement_logic(db: Session, settlement: FinalSettlement):
    # Business logic: Leave encashment, Gratuity, Notice pay, etc.
    # Simplified for implementation
    settlement.total_earnings = settlement.leave_encashment_amount + settlement.bonus_amount
    settlement.total_recoveries = settlement.asset_recovery + settlement.loan_recovery + settlement.notice_pay_recovery
    settlement.net_settlement_amount = settlement.total_earnings - settlement.total_recoveries - settlement.tax_deducted
    db.commit()
    db.refresh(settlement)

@router.get("/", response_model=FinalSettlementListResponse)
def get_settlements(
    page: int = Query(1, ge=1),
    limit: int = Query(10, ge=1, le=100),
    search: Optional[str] = None,
    employee_id: Optional[int] = None,
    status: Optional[str] = None,
    db: Session = Depends(deps.get_db),
    current_user: Union[Organization, Employee] = Depends(deps.get_current_user)
):
    _require_permission(db, current_user, "128", "list")
    org_id = _get_org_id(current_user)
    query = db.query(FinalSettlement).filter(FinalSettlement.organization_id == org_id)
    
    if employee_id: query = query.filter(FinalSettlement.employee_id == employee_id)
    if status: query = query.filter(FinalSettlement.status == status)
    if search:
        query = query.join(Employee, FinalSettlement.employee_id == Employee.id).filter(
            or_(
                FinalSettlement.settlement_number.ilike(f"%{search}%"),
                Employee.first_name.ilike(f"%{search}%"),
                Employee.last_name.ilike(f"%{search}%")
            )
        )
    
    total = query.count()
    items = query.offset((page - 1) * limit).limit(limit).all()
    return FinalSettlementListResponse(success=True, message="Retrieved", data=items, pagination={"total_records": total, "current_page": page, "total_pages": (total + limit - 1) // limit, "page_size": limit})

@router.post("/", response_model=FinalSettlementResponse)
def create_settlement(
    item_in: FinalSettlementCreate,
    db: Session = Depends(deps.get_db),
    current_user: Union[Organization, Employee] = Depends(deps.get_current_user)
):
    _require_permission(db, current_user, "129", "create")
    org_id = _get_org_id(current_user)
    
    emp = db.query(Employee).filter(Employee.uuid == item_in.employee_uuid, Employee.organization_id == org_id).first()
    if not emp:
        raise HTTPException(404, "Employee not found")
        
    if db.query(FinalSettlement).filter(FinalSettlement.employee_id == emp.id).first():
        raise HTTPException(400, "Settlement already exists for this employee")
    
    # Atomic number generation
    year = datetime.utcnow().year
    count = db.query(func.count(FinalSettlement.id)).filter(FinalSettlement.organization_id == org_id).scalar() + 1
    settlement_number = f"FS-{emp.employee_code or emp.id}-{year}-{count}"
    
    item = FinalSettlement(
        organization_id=org_id,
        employee_id=emp.id,
        settlement_number=settlement_number,
        total_years=0,
        total_months=0,
        total_days=0,
        last_month_days_worked=0,
        last_month_salary=0,
        leave_balance_days=0,
        notice_period_days=0,
        notice_period_served=0,
        total_earnings=0,
        total_deductions=0,
        net_settlement_amount=0,
        **item_in.model_dump(exclude={'employee_uuid'})
    )
    db.add(item)
    db.commit()
    db.refresh(item)
    calculate_settlement_logic(db, item)
    return {"success": True, "message": "Created", "data": item}


@router.get("/{settlement_uuid}", response_model=FinalSettlementResponse)
def get_settlement(settlement_uuid: uuid.UUID, db: Session = Depends(deps.get_db), current_user: Union[Organization, Employee] = Depends(deps.get_current_user)):
    item = db.query(FinalSettlement).filter(FinalSettlement.uuid == settlement_uuid, FinalSettlement.organization_id == _get_org_id(current_user)).first()
    if not item: raise HTTPException(404, "Not found")
    return {"success": True, "message": "Retrieved", "data": item}

@router.put("/{settlement_uuid}", response_model=FinalSettlementResponse)
def update_settlement(settlement_uuid: uuid.UUID, item_in: FinalSettlementUpdate, db: Session = Depends(deps.get_db), current_user: Union[Organization, Employee] = Depends(deps.get_current_user)):
    item = db.query(FinalSettlement).filter(FinalSettlement.uuid == settlement_uuid, FinalSettlement.organization_id == _get_org_id(current_user)).first()
    if not item: raise HTTPException(404, "Not found")
    for k, v in item_in.model_dump(exclude_unset=True).items(): setattr(item, k, v)
    db.commit()
    db.refresh(item)
    return {"success": True, "message": "Updated", "data": item}

@router.post("/{settlement_uuid}/calculate", response_model=FinalSettlementResponse)
def calculate_settlement(settlement_uuid: uuid.UUID, db: Session = Depends(deps.get_db), current_user: Union[Organization, Employee] = Depends(deps.get_current_user)):
    item = db.query(FinalSettlement).filter(FinalSettlement.uuid == settlement_uuid, FinalSettlement.organization_id == _get_org_id(current_user)).first()
    if not item: raise HTTPException(404, "Not found")
    calculate_settlement_logic(db, item)
    return {"success": True, "message": "Calculated", "data": item}

@router.post("/{settlement_uuid}/approve", response_model=FinalSettlementResponse)
def approve_settlement(settlement_uuid: uuid.UUID, item_in: SettlementApprovalUpdate, db: Session = Depends(deps.get_db), current_user: Union[Organization, Employee] = Depends(deps.get_current_user)):
    _require_permission(db, current_user, "130", "approve")
    item = db.query(FinalSettlement).filter(FinalSettlement.uuid == settlement_uuid, FinalSettlement.organization_id == _get_org_id(current_user)).first()
    if not item: raise HTTPException(404, "Not found")
    item.status = "approved"
    item.approved_at = datetime.utcnow()
    item.approval_comments = item_in.approval_comments
    db.commit()
    return {"success": True, "message": "Approved", "data": item}

@router.post("/{settlement_uuid}/process-payment", response_model=FinalSettlementResponse)
def process_payment(settlement_uuid: uuid.UUID, item_in: SettlementPaymentUpdate, db: Session = Depends(deps.get_db), current_user: Union[Organization, Employee] = Depends(deps.get_current_user)):
    item = db.query(FinalSettlement).filter(FinalSettlement.uuid == settlement_uuid, FinalSettlement.organization_id == _get_org_id(current_user)).first()
    if not item or item.status != "approved": raise HTTPException(400, "Invalid status")
    item.status = "paid"
    item.paid_at = datetime.utcnow()
    item.payment_mode = item_in.payment_mode
    item.payment_reference = item_in.payment_reference
    db.commit()
    return {"success": True, "message": "Paid", "data": item}


@router.get("/{settlement_uuid}/download")
def download_settlement(
    settlement_uuid: uuid.UUID,
    db: Session = Depends(deps.get_db),
    current_user: Union[Organization, Employee] = Depends(deps.get_current_user)
):
    org_id = _get_org_id(current_user)
    
    # Query FinalSettlement joined with Employee and Organization
    result = db.query(FinalSettlement, Employee, Organization)\
        .join(Employee, FinalSettlement.employee_id == Employee.id)\
        .join(Organization, FinalSettlement.organization_id == Organization.id)\
        .filter(FinalSettlement.uuid == settlement_uuid, FinalSettlement.organization_id == org_id).first()
        
    if not result:
        raise HTTPException(status_code=404, detail="Final Settlement not found")
        
    settlement, emp, org = result
    
    # Access checks: Non-admin employees can only download their own statement
    if not isinstance(current_user, Organization) and settlement.employee_id != current_user.id:
        if not deps.has_permission(db, current_user, "128"):
            raise HTTPException(status_code=403, detail="Not authorized to download this final settlement")

    # Fetch employee designation & department using property fields
    dept_name = emp.department_name or "N/A"
    desig_name = emp.job_title_name or "Employee"
    
    # Format tenure summary
    tenure_list = []
    if settlement.total_years > 0:
        tenure_list.append(f"{settlement.total_years} years")
    if settlement.total_months > 0:
        tenure_list.append(f"{settlement.total_months} months")
    tenure_list.append(f"{settlement.total_days} days")
    tenure_summary = ", ".join(tenure_list)
    
    # Save the generated PDF file path inside a temporary mock directory
    base_dir = os.path.dirname(os.path.abspath(__file__))
    mock_dir = os.path.join(base_dir, "..", "..", "..", "..", "mock_files", "final_settlements")
    os.makedirs(mock_dir, exist_ok=True)
    file_path = os.path.join(mock_dir, f"{settlement.uuid}.pdf")
    
    # Format dates
    settlement_date_str = settlement.settlement_date.strftime("%Y-%m-%d") if settlement.settlement_date else "N/A"
    lwd_str = settlement.last_working_date.strftime("%Y-%m-%d") if settlement.last_working_date else "N/A"
    
    pdf_data = {
        "organization_name": org.name,
        "employee_name": f"{emp.first_name} {emp.last_name}",
        "employee_code": emp.employee_code or f"EMP-{emp.id}",
        "department_name": dept_name,
        "designation": desig_name,
        "settlement_number": settlement.settlement_number,
        "settlement_date": settlement_date_str,
        "last_working_date": lwd_str,
        "separation_type": settlement.separation_type.title() if settlement.separation_type else "N/A",
        "tenure_summary": tenure_summary,
        "last_month_salary": float(settlement.last_month_salary or 0),
        "leave_balance_days": float(settlement.leave_balance_days or 0),
        "leave_encashment_amount": float(settlement.leave_encashment_amount or 0),
        "gratuity_amount": float(settlement.gratuity_amount or 0),
        "bonus_amount": float(settlement.bonus_amount or 0),
        "pending_reimbursements": float(settlement.pending_reimbursements or 0),
        "total_recoveries": float(settlement.total_recoveries or 0),
        "tax_deducted": float(settlement.tax_deducted or 0),
        "notice_pay_recovery": float(settlement.notice_pay_recovery or 0),
        "net_settlement_amount": float(settlement.net_settlement_amount or 0),
        "notes": settlement.notes,
        "approval_comments": settlement.approval_comments,
        "payment_mode": settlement.payment_mode.replace("_", " ").title() if settlement.payment_mode else None,
        "payment_reference": settlement.payment_reference
    }
    
    html = get_final_settlement_html(pdf_data)
    pdf_content = generate_pdf(html)
    
    if pdf_content:
        with open(file_path, "wb") as f:
            f.write(pdf_content.getvalue())
    else:
        raise HTTPException(status_code=500, detail="Failed to generate PDF content")
        
    return FileResponse(
        path=file_path,
        filename=f"settlement_{settlement.settlement_number}.pdf",
        media_type="application/pdf"
    )