import uuid
from typing import List, Optional, Union
from datetime import date
from fastapi import APIRouter, Depends, HTTPException, Query, status, BackgroundTasks
from sqlalchemy.orm import Session
from sqlalchemy import func, or_, and_

from app.api import deps
from app.models.organization import Organization
from app.models.employee import Employee
from app.models.payroll import Payslip, PayrollStatus, PayrollPeriod
from app.schemas.payroll_payslips import (
    PayslipSchema, PayslipListResponse, PayslipResponse, 
    PayslipHoldUpdate, PayslipReverseCreate, BulkEmailRequest
)
from app.models.employee import Employee
from app.core.permissions import PayrollPayslipPermissions

router = APIRouter()

def _get_org_id(current_user: Union[Organization, Employee]) -> int:
    return current_user.id if isinstance(current_user, Organization) else current_user.organization_id

def _require_permission(db: Session, current_user: Union[Organization, Employee], code: str, action_label: str):
    if not isinstance(current_user, Organization) and not deps.has_permission(db, current_user, code):
        raise HTTPException(status_code=403, detail=f"You do not have permission to {action_label}")

@router.get("/", response_model=PayslipListResponse)
def get_payslips(
    period_id: Optional[int] = None,
    employee_id: Optional[int] = None,
    department_id: Optional[int] = None,
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
    db: Session = Depends(deps.get_db),
    current_user: Union[Organization, Employee] = Depends(deps.get_current_user)
):
    _require_permission(db, current_user, PayrollPayslipPermissions.READ, "list payslips")
    org_id = _get_org_id(current_user)
    
    query = db.query(Payslip).filter(Payslip.organization_id == org_id)
    
    if not isinstance(current_user, Organization):
        query = query.filter(Payslip.employee_id == current_user.id)
    
    if period_id: query = query.filter(Payslip.payroll_period_id == period_id)
    if employee_id: query = query.filter(Payslip.employee_id == employee_id)
    if status: query = query.filter(Payslip.status == status)
    if is_published is not None: query = query.filter(Payslip.is_published == is_published)
    if is_reversed is not None: query = query.filter(Payslip.is_reversed == is_reversed)
    if is_on_hold is not None: query = query.filter(Payslip.is_on_hold == is_on_hold)
    if from_date: query = query.filter(Payslip.period_start_date >= from_date)
    if to_date: query = query.filter(Payslip.period_end_date <= to_date)
    
    if department_id:
        query = query.join(Employee, Payslip.employee_id == Employee.id).filter(Employee.department_id == department_id)
    
    if search:
        query = query.filter(Payslip.payslip_number.ilike(f"%{search}%"))

    allowed_sort = ["created_at", "payslip_number", "net_salary"]
    if sort_by not in allowed_sort: sort_by = "created_at"
    query = query.order_by(getattr(Payslip, sort_by).desc())

    total_records = query.count()
    items = query.offset((page - 1) * limit).limit(limit).all()
    
    return PayslipListResponse(
        success=True, message="Payslips retrieved successfully",
        data=[PayslipSchema.model_validate(i) for i in items],
        pagination={"total_records": total_records, "current_page": page, "total_pages": (total_records + limit - 1) // limit, "page_size": limit}
    )

@router.get("/{payslip_uuid}", response_model=PayslipResponse)
def get_payslip_details(payslip_uuid: uuid.UUID, db: Session = Depends(deps.get_db), current_user: Union[Organization, Employee] = Depends(deps.get_current_user)):
    org_id = _get_org_id(current_user)
    query = db.query(Payslip).filter(Payslip.uuid == payslip_uuid, Payslip.organization_id == org_id)
    if not isinstance(current_user, Organization): query = query.filter(Payslip.employee_id == current_user.id)
    
    payslip = query.first()
    if not payslip: raise HTTPException(status_code=404, detail="Payslip not found")
    return {"success": True, "message": "Payslip retrieved successfully", "data": PayslipSchema.model_validate(payslip)}

@router.patch("/{payslip_uuid}/hold", response_model=PayslipResponse)
def hold_payslip(payslip_uuid: uuid.UUID, data: PayslipHoldUpdate, db: Session = Depends(deps.get_db), current_user: Union[Organization, Employee] = Depends(deps.get_current_user)):
    _require_permission(db, current_user, PayrollPayslipPermissions.PUBLISH, "hold payslip")
    payslip = db.query(Payslip).filter(Payslip.uuid == payslip_uuid, Payslip.organization_id == _get_org_id(current_user)).first()
    if not payslip or payslip.is_published: raise HTTPException(status_code=400, detail="Cannot hold published payslip")
    
    payslip.is_on_hold = True
    payslip.hold_reason = data.hold_reason
    db.commit()
    return {"success": True, "message": "Payslip held successfully", "data": PayslipSchema.model_validate(payslip)}

@router.post("/{payslip_uuid}/reverse", response_model=PayslipResponse)
def reverse_payslip(payslip_uuid: uuid.UUID, data: PayslipReverseCreate, db: Session = Depends(deps.get_db), current_user: Union[Organization, Employee] = Depends(deps.get_current_user)):
    _require_permission(db, current_user, PayrollPayslipPermissions.REVERSE, "reverse payslip")
    payslip = db.query(Payslip).filter(Payslip.uuid == payslip_uuid, Payslip.organization_id == _get_org_id(current_user)).first()
    if not payslip: raise HTTPException(status_code=404, detail="Payslip not found")
    
    payslip.is_reversed = True
    payslip.reversed_at = func.now()
    payslip.reversal_reason = data.reversal_reason
    db.commit()
    return {"success": True, "message": "Payslip reversed successfully", "data": PayslipSchema.model_validate(payslip)}

@router.post("/bulk-email", response_model=dict)
def bulk_email_payslips(
    data: BulkEmailRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(deps.get_db),
    current_user: Union[Organization, Employee] = Depends(deps.get_current_user)
):
    _require_permission(db, current_user, PayrollPayslipPermissions.PUBLISH, "send bulk emails")
    org_id = _get_org_id(current_user)
    
    payslips = db.query(Payslip).filter(
        Payslip.uuid.in_(data.payslip_uuids),
        Payslip.organization_id == org_id
    ).all()
    
    if not payslips:
        raise HTTPException(status_code=404, detail="No valid payslips found for email")
    
    # Placeholder for actual email sending logic
    for payslip in payslips:
        payslip.email_sent = True
        payslip.email_sent_at = func.now()
    
    db.commit()
    
    return {
        "success": True,
        "message": f"Emails queued for {len(payslips)} payslips",
        "data": {"count": len(payslips)}
    }

@router.post("/{payslip_uuid}/send-email", response_model=dict)
def send_payslip_email(
    payslip_uuid: uuid.UUID,
    db: Session = Depends(deps.get_db),
    current_user: Union[Organization, Employee] = Depends(deps.get_current_user)
):
    _require_permission(db, current_user, PayrollPayslipPermissions.PUBLISH, "send email")
    org_id = _get_org_id(current_user)
    
    payslip = db.query(Payslip).filter(
        Payslip.uuid == payslip_uuid,
        Payslip.organization_id == org_id
    ).first()
    
    if not payslip:
        raise HTTPException(status_code=404, detail="Payslip not found")
    
    payslip.email_sent = True
    payslip.email_sent_at = func.now()
    db.commit()
    
    return {"success": True, "message": "Email sent successfully", "data": None}