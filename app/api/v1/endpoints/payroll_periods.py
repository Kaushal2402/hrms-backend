import uuid
from typing import List, Optional, Union
from fastapi import APIRouter, Depends, HTTPException, Query, status, BackgroundTasks
from sqlalchemy.orm import Session
from sqlalchemy import func, or_

from app.api import deps
from app.models.organization import Organization
from app.models.employee import Employee
from app.models.payroll import PayrollPeriod, PayrollStatus
from app.schemas.payroll_periods import (
    PayrollPeriodCreate, PayrollPeriodUpdate, PayrollPeriodSchema, 
    PayrollPeriodResponse, PayrollPeriodListResponse, PayrollPeriodAction,
    PayrollSummaryResponse
)
from app.core.permissions import PayrollPeriodPermissions

router = APIRouter()


def _get_org_id(current_user: Union[Organization, Employee]) -> int:
    return current_user.id if isinstance(current_user, Organization) else current_user.organization_id

def _require_permission(db, current_user, code, action_label):
    if isinstance(current_user, Organization): return
    if not deps.has_permission(db, current_user, code):
        raise HTTPException(status_code=403, detail=f"Permission denied: {action_label}")

@router.get("/", response_model=PayrollPeriodListResponse)
def get_payroll_periods(
    page: int = Query(1, ge=1),
    limit: int = Query(10, ge=1, le=100),
    search: Optional[str] = None,
    status: Optional[PayrollStatus] = None,
    financial_year: Optional[str] = None,
    db: Session = Depends(deps.get_db),
    current_user: Union[Organization, Employee] = Depends(deps.get_current_user)
):
    _require_permission(db, current_user, PayrollPeriodPermissions.READ, "list")
    org_id = _get_org_id(current_user)
    query = db.query(PayrollPeriod).filter(PayrollPeriod.organization_id == org_id)
    
    if search:
        query = query.filter(or_(PayrollPeriod.period_name.ilike(f"%{search}%"), PayrollPeriod.period_code.ilike(f"%{search}%")))
    if status: query = query.filter(PayrollPeriod.status == status)
    if financial_year: query = query.filter(PayrollPeriod.financial_year == financial_year)
    
    total = query.count()
    items = query.offset((page - 1) * limit).limit(limit).all()
    return {"success": True, "message": "Retrieved successfully", "data": items, "pagination": {"total_records": total, "current_page": page, "total_pages": (total + limit - 1) // limit, "page_size": limit}}

@router.post("/", response_model=PayrollPeriodResponse)
def create_payroll_period(item_in: PayrollPeriodCreate, db: Session = Depends(deps.get_db), current_user: Union[Organization, Employee] = Depends(deps.get_current_user)):
    _require_permission(db, current_user, PayrollPeriodPermissions.CREATE, "create")
    org_id = _get_org_id(current_user)
    if db.query(PayrollPeriod).filter(PayrollPeriod.organization_id == org_id, PayrollPeriod.period_code == item_in.period_code).first():
        raise HTTPException(400, "Period code already exists")
    item = PayrollPeriod(organization_id=org_id, **item_in.model_dump())
    db.add(item); db.commit(); db.refresh(item)
    return {"success": True, "message": "Created successfully", "data": item}

@router.get("/{period_uuid}", response_model=PayrollPeriodResponse)
def get_period(period_uuid: uuid.UUID, db: Session = Depends(deps.get_db), current_user: Union[Organization, Employee] = Depends(deps.get_current_user)):
    _require_permission(db, current_user, PayrollPeriodPermissions.READ, "view")
    item = db.query(PayrollPeriod).filter(PayrollPeriod.uuid == period_uuid, PayrollPeriod.organization_id == _get_org_id(current_user)).first()
    if not item: raise HTTPException(404, "Period not found")
    return {"success": True, "message": "Retrieved successfully", "data": item}

@router.put("/{period_uuid}", response_model=PayrollPeriodResponse)
def update_period(period_uuid: uuid.UUID, item_in: PayrollPeriodUpdate, db: Session = Depends(deps.get_db), current_user: Union[Organization, Employee] = Depends(deps.get_current_user)):
    _require_permission(db, current_user, PayrollPeriodPermissions.UPDATE, "update")
    item = db.query(PayrollPeriod).filter(PayrollPeriod.uuid == period_uuid, PayrollPeriod.organization_id == _get_org_id(current_user)).first()
    if not item or item.is_locked: raise HTTPException(400, "Period not found or locked")
    for f, v in item_in.model_dump(exclude_unset=True).items(): setattr(item, f, v)
    db.commit(); db.refresh(item)
    return {"success": True, "message": "Updated successfully", "data": item}

@router.post("/{period_uuid}/process", response_model=PayrollPeriodResponse)
def process_payroll(period_uuid: uuid.UUID, background_tasks: BackgroundTasks, should_proceed_background: bool = Query(False), db: Session = Depends(deps.get_db), current_user: Union[Organization, Employee] = Depends(deps.get_current_user)):
    _require_permission(db, current_user, PayrollPeriodPermissions.PROCESS, "process")
    item = db.query(PayrollPeriod).filter(PayrollPeriod.uuid == period_uuid, PayrollPeriod.organization_id == _get_org_id(current_user)).first()
    if not item or item.status not in [PayrollStatus.DRAFT, PayrollStatus.IN_PROGRESS]: raise HTTPException(400, "Invalid status for processing")
    item.status = PayrollStatus.IN_PROGRESS
    db.commit()
    # Logic for processing would go here
    return {"success": True, "message": "Processing initiated", "data": item}

@router.get("/{period_uuid}/summary", response_model=PayrollSummaryResponse)
def get_summary(period_uuid: uuid.UUID, db: Session = Depends(deps.get_db), current_user: Union[Organization, Employee] = Depends(deps.get_current_user)):
    item = db.query(PayrollPeriod).filter(PayrollPeriod.uuid == period_uuid, PayrollPeriod.organization_id == _get_org_id(current_user)).first()
    if not item: raise HTTPException(404, "Period not found")
    return {"success": True, "message": "Summary retrieved", "data": {"total_employees": item.total_employees, "total_net": item.total_net_amount}}

@router.post("/{period_uuid}/submit-approval", response_model=PayrollPeriodResponse)
def submit_for_approval(
    period_uuid: uuid.UUID, 
    data: PayrollPeriodAction,
    db: Session = Depends(deps.get_db), 
    current_user: Union[Organization, Employee] = Depends(deps.get_current_user)
):
    _require_permission(db, current_user, PayrollPeriodPermissions.PROCESS, "submit for approval")
    org_id = _get_org_id(current_user)
    item = db.query(PayrollPeriod).filter(PayrollPeriod.uuid == period_uuid, PayrollPeriod.organization_id == org_id).first()
    if not item: raise HTTPException(404, "Period not found")
    
    if item.status not in [PayrollStatus.DRAFT, PayrollStatus.IN_PROGRESS]:
        raise HTTPException(400, f"Cannot submit for approval from status: {item.status}")
    
    item.status = PayrollStatus.PENDING_APPROVAL
    item.submitted_for_approval_at = func.now()
    if not isinstance(current_user, Organization):
        item.submitted_by = current_user.id
    
    db.commit()
    db.refresh(item)
    return {"success": True, "message": "Payroll submitted for approval", "data": item}

@router.post("/{period_uuid}/approve", response_model=PayrollPeriodResponse)
def approve_payroll(
    period_uuid: uuid.UUID, 
    data: PayrollPeriodAction,
    db: Session = Depends(deps.get_db), 
    current_user: Union[Organization, Employee] = Depends(deps.get_current_user)
):
    _require_permission(db, current_user, PayrollPeriodPermissions.PROCESS, "approve payroll")
    org_id = _get_org_id(current_user)
    item = db.query(PayrollPeriod).filter(PayrollPeriod.uuid == period_uuid, PayrollPeriod.organization_id == org_id).first()
    if not item: raise HTTPException(404, "Period not found")
    
    if item.status != PayrollStatus.PENDING_APPROVAL:
        raise HTTPException(400, "Only pending approval periods can be approved")
    
    item.status = PayrollStatus.APPROVED
    item.approved_at = func.now()
    item.approval_comments = data.comments
    if not isinstance(current_user, Organization):
        item.approved_by = current_user.id
    
    db.commit()
    db.refresh(item)
    return {"success": True, "message": "Payroll approved successfully", "data": item}

@router.post("/{period_uuid}/publish", response_model=PayrollPeriodResponse)
def publish_payroll(
    period_uuid: uuid.UUID, 
    db: Session = Depends(deps.get_db), 
    current_user: Union[Organization, Employee] = Depends(deps.get_current_user)
):
    _require_permission(db, current_user, PayrollPeriodPermissions.PROCESS, "publish payroll")
    org_id = _get_org_id(current_user)
    item = db.query(PayrollPeriod).filter(PayrollPeriod.uuid == period_uuid, PayrollPeriod.organization_id == org_id).first()
    if not item: raise HTTPException(404, "Period not found")
    
    if item.status != PayrollStatus.APPROVED:
        raise HTTPException(400, "Only approved periods can be published")
    
    item.status = PayrollStatus.PUBLISHED
    item.published_at = func.now()
    if not isinstance(current_user, Organization):
        item.published_by = current_user.id
    
    db.commit()
    db.refresh(item)
    return {"success": True, "message": "Payroll published successfully", "data": item}

@router.post("/{period_uuid}/lock", response_model=PayrollPeriodResponse)
def lock_period(
    period_uuid: uuid.UUID, 
    db: Session = Depends(deps.get_db), 
    current_user: Union[Organization, Employee] = Depends(deps.get_current_user)
):
    _require_permission(db, current_user, PayrollPeriodPermissions.PROCESS, "lock period")
    org_id = _get_org_id(current_user)
    item = db.query(PayrollPeriod).filter(PayrollPeriod.uuid == period_uuid, PayrollPeriod.organization_id == org_id).first()
    if not item: raise HTTPException(404, "Period not found")
    
    item.is_locked = True
    item.locked_at = func.now()
    if not isinstance(current_user, Organization):
        item.locked_by = current_user.id
    
    db.commit()
    db.refresh(item)
    return {"success": True, "message": "Period locked successfully", "data": item}

@router.post("/{period_uuid}/unlock", response_model=PayrollPeriodResponse)
def unlock_period(
    period_uuid: uuid.UUID, 
    db: Session = Depends(deps.get_db), 
    current_user: Union[Organization, Employee] = Depends(deps.get_current_user)
):
    _require_permission(db, current_user, PayrollPeriodPermissions.PROCESS, "unlock period")
    org_id = _get_org_id(current_user)
    item = db.query(PayrollPeriod).filter(PayrollPeriod.uuid == period_uuid, PayrollPeriod.organization_id == org_id).first()
    if not item: raise HTTPException(404, "Period not found")
    
    item.is_locked = False
    item.locked_at = None
    item.locked_by = None
    
    db.commit()
    db.refresh(item)
    return {"success": True, "message": "Period unlocked successfully", "data": item}

@router.post("/{period_uuid}/hold", response_model=PayrollPeriodResponse)
def hold_period(
    period_uuid: uuid.UUID, 
    data: PayrollPeriodAction,
    db: Session = Depends(deps.get_db), 
    current_user: Union[Organization, Employee] = Depends(deps.get_current_user)
):
    _require_permission(db, current_user, PayrollPeriodPermissions.PROCESS, "hold period")
    org_id = _get_org_id(current_user)
    item = db.query(PayrollPeriod).filter(PayrollPeriod.uuid == period_uuid, PayrollPeriod.organization_id == org_id).first()
    if not item: raise HTTPException(404, "Period not found")
    
    item.status = PayrollStatus.ON_HOLD
    item.is_on_hold = True
    item.hold_reason = data.reason or data.comments
    
    db.commit()
    db.refresh(item)
    return {"success": True, "message": "Payroll period put on hold", "data": item}

@router.post("/{period_uuid}/reverse", response_model=PayrollPeriodResponse)
def reverse_period(
    period_uuid: uuid.UUID, 
    data: PayrollPeriodAction,
    db: Session = Depends(deps.get_db), 
    current_user: Union[Organization, Employee] = Depends(deps.get_current_user)
):
    _require_permission(db, current_user, PayrollPeriodPermissions.PROCESS, "reverse period")
    org_id = _get_org_id(current_user)
    item = db.query(PayrollPeriod).filter(PayrollPeriod.uuid == period_uuid, PayrollPeriod.organization_id == org_id).first()
    if not item: raise HTTPException(404, "Period not found")
    
    if item.status not in [PayrollStatus.PROCESSED, PayrollStatus.PAID, PayrollStatus.PUBLISHED]:
        raise HTTPException(400, "Only processed, paid or published periods can be reversed")
    
    item.status = PayrollStatus.REVERSED
    # Logic for reversing individual payslips would ideally be triggered here
    
    db.commit()
    db.refresh(item)
    return {"success": True, "message": "Payroll period reversed", "data": item}