from decimal import Decimal
import uuid
from typing import List, Optional, Union
from fastapi import APIRouter, Depends, HTTPException, Query, status, BackgroundTasks
from sqlalchemy.orm import Session
from sqlalchemy import func, or_

from app.api import deps
from app.models.organization import Organization
from app.models.employee import Employee
from app.models.payroll import (
    PayrollPeriod, PayrollStatus, EmployeeSalary, 
    EmployeeSalaryComponent, Payslip, PayslipComponent, 
    PayslipStatus, ComponentType
)
from app.schemas.payroll_periods import (
    PayrollPeriodCreate, PayrollPeriodUpdate, PayrollPeriodSchema, 
    PayrollPeriodResponse, PayrollPeriodListResponse, PayrollPeriodAction,
    PayrollSummaryResponse, PayrollPeriodLookupResponse
)
from app.core.permissions import PayrollPeriodPermissions
from app.utils.payroll_audit import PayrollAuditService

router = APIRouter()


def _get_org_id(current_user: Union[Organization, Employee]) -> int:
    return current_user.id if isinstance(current_user, Organization) else current_user.organization_id

def _require_permission(db, current_user, code, action_label):
    if isinstance(current_user, Organization): return
    if not deps.has_permission(db, current_user, code):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=f"Permission denied: {action_label}")

@router.get("/lookup", response_model=PayrollPeriodLookupResponse)
def get_payroll_periods_lookup(
    db: Session = Depends(deps.get_db),
    current_user: Union[Organization, Employee] = Depends(deps.get_current_user)
):
    """Lighweight lookup for payroll periods (No permission check)"""
    org_id = _get_org_id(current_user)
    periods = db.query(PayrollPeriod).filter(
        PayrollPeriod.organization_id == org_id
    ).order_by(PayrollPeriod.period_start_date.desc()).all()
    
    return {
        "success": True,
        "message": "Lookup retrieved successfully",
        "data": periods
    }

@router.get("/", response_model=PayrollPeriodListResponse)
def get_payroll_periods(
    page: int = Query(1, ge=1),
    limit: int = Query(10, ge=1, le=100),
    search: Optional[str] = None,
    status: Optional[PayrollStatus] = None,
    financial_year: Optional[str] = None,
    sort_by: str = Query("created_at"),
    sort_order: str = Query("desc"),
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
    
    # Apply Sorting
    if hasattr(PayrollPeriod, sort_by):
        column = getattr(PayrollPeriod, sort_by)
        if sort_order == "desc":
            query = query.order_by(column.desc())
        else:
            query = query.order_by(column.asc())
    else:
        query = query.order_by(PayrollPeriod.created_at.desc())
    
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
    period = db.query(PayrollPeriod).filter(PayrollPeriod.uuid == period_uuid, PayrollPeriod.organization_id == _get_org_id(current_user)).first()
    if not period or period.is_locked: raise HTTPException(400, "Period not found or locked")
    if period.status != PayrollStatus.DRAFT:
        raise HTTPException(status_code=400, detail="Only draft periods can be updated")

    before_state = PayrollAuditService.get_model_dict(period)
    for f, v in item_in.model_dump(exclude_unset=True).items(): setattr(period, f, v)
    db.commit(); db.refresh(period)

    PayrollAuditService.log(
        db=db,
        current_user=current_user,
        action_type="period_updated",
        entity_type="payroll_period",
        entity_id=period.id,
        before_state=before_state,
        after_state=PayrollAuditService.get_model_dict(period),
        risk_level="medium",
        change_summary=f"Updated payroll period {period.period_name}"
    )
    return {"success": True, "message": "Updated successfully", "data": PayrollPeriodSchema.model_validate(period)}

@router.post("/{period_uuid}/process", response_model=PayrollPeriodResponse)
def process_payroll(
    period_uuid: uuid.UUID, 
    data: PayrollPeriodAction,
    db: Session = Depends(deps.get_db), 
    current_user: Union[Organization, Employee] = Depends(deps.get_current_user)
):
    _require_permission(db, current_user, PayrollPeriodPermissions.PROCESS, "process")
    org_id = _get_org_id(current_user)
    period = db.query(PayrollPeriod).filter(PayrollPeriod.uuid == period_uuid, PayrollPeriod.organization_id == org_id).first()
    if not period: raise HTTPException(404, "Period not found")
    
    if period.status.value != PayrollStatus.APPROVED.value:
        raise HTTPException(400, f"Only approved periods can be processed. Current status: {period.status}")
    
    # 1. Clear existing payslips for re-processing
    db.query(PayslipComponent).filter(
        PayslipComponent.payslip_id.in_(
            db.query(Payslip.id).filter(Payslip.payroll_period_id == period.id)
        )
    ).delete(synchronize_session=False)
    db.query(Payslip).filter(Payslip.payroll_period_id == period.id).delete(synchronize_session=False)
    
    # 2. Fetch all eligible employees
    salaries = db.query(EmployeeSalary).filter(
        EmployeeSalary.organization_id == org_id,
        EmployeeSalary.is_active == True,
        EmployeeSalary.is_on_hold == False
    ).all()
    
    total_gross = 0
    total_deductions = 0
    total_net = 0
    total_employer_contrib = 0
    headcount = 0
    
    # 3. Generate Payslips
    for salary in salaries:
        payslip = Payslip(
            organization_id=org_id,
            payroll_period_id=period.id,
            employee_id=salary.employee_id,
            employee_salary_id=salary.id,
            payslip_number=f"PS-{org_id}-{period.period_code}-{salary.employee_id}-{uuid.uuid4().hex[:4]}",
            period_start_date=period.period_start_date,
            period_end_date=period.period_end_date,
            payment_date=period.payment_date,
            total_working_days=period.total_working_days,
            paid_days=period.total_working_days,
            days_present=period.total_working_days,
            basic_salary=salary.monthly_gross * Decimal("0.5"),
            gross_salary=salary.monthly_gross,
            total_earnings=salary.monthly_gross,
            total_deductions=salary.monthly_gross - salary.monthly_net,
            net_salary=salary.monthly_net,
            monthly_ctc=salary.monthly_ctc,
            status=PayslipStatus.GENERATED,
            is_published=False
        )
        db.add(payslip)
        db.flush() 
        
        comp_query = db.query(EmployeeSalaryComponent).filter(EmployeeSalaryComponent.employee_salary_id == salary.id)
        for esc in comp_query.all():
            ps_comp = PayslipComponent(
                payslip_id=payslip.id,
                component_id=esc.component_id,
                component_name="Component",
                component_type=ComponentType.EARNING,
                monthly_amount=esc.monthly_amount,
                actual_amount=esc.monthly_amount
            )
            db.add(ps_comp)
            
        total_gross += salary.monthly_gross
        total_deductions += (salary.monthly_gross - salary.monthly_net)
        total_net += salary.monthly_net
        total_employer_contrib += (salary.monthly_ctc - salary.monthly_gross)
        headcount += 1
        
    period.total_employees = headcount
    period.total_gross_amount = total_gross
    period.total_deductions = total_deductions
    period.total_net_amount = total_net
    period.total_employer_contributions = total_employer_contrib
    
    before_state = PayrollAuditService.get_model_dict(period)
    period.status = PayrollStatus.PROCESSED
    period.processing_completed_at = func.now()
    if not isinstance(current_user, Organization):
        period.processed_by = current_user.id
    
    db.commit()
    db.refresh(period)

    PayrollAuditService.log(
        db=db,
        current_user=current_user,
        action_type="period_processed",
        entity_type="payroll_period",
        entity_id=period.id,
        before_state=before_state,
        after_state=PayrollAuditService.get_model_dict(period),
        risk_level="high",
        change_summary=f"Processed payroll period {period.period_name}"
    )
    return {"success": True, "message": f"Payroll processed successfully. {headcount} payslips generated.", "data": PayrollPeriodSchema.model_validate(period)}

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
    period = db.query(PayrollPeriod).filter(PayrollPeriod.uuid == period_uuid, PayrollPeriod.organization_id == org_id).first()
    if not period: raise HTTPException(404, "Period not found")
    
    if period.status != PayrollStatus.PROCESSED:
        raise HTTPException(400, f"Cannot submit for approval from status: {period.status}")
    
    before_state = PayrollAuditService.get_model_dict(period)
    period.status = PayrollStatus.PENDING_APPROVAL
    period.submitted_for_approval_at = func.now()
    if not isinstance(current_user, Organization):
        period.submitted_by = current_user.id
    
    db.commit()
    db.refresh(period)

    PayrollAuditService.log(
        db=db,
        current_user=current_user,
        action_type="period_submitted",
        entity_type="payroll_period",
        entity_id=period.id,
        before_state=before_state,
        after_state=PayrollAuditService.get_model_dict(period),
        risk_level="medium",
        change_summary=f"Submitted payroll period {period.period_name} for approval"
    )
    return {"success": True, "message": "Payroll submitted for approval", "data": PayrollPeriodSchema.model_validate(period)}

@router.post("/{period_uuid}/approve", response_model=PayrollPeriodResponse)
def approve_payroll(
    period_uuid: uuid.UUID, 
    data: PayrollPeriodAction,
    db: Session = Depends(deps.get_db), 
    current_user: Union[Organization, Employee] = Depends(deps.get_current_user)
):
    _require_permission(db, current_user, PayrollPeriodPermissions.PROCESS, "approve payroll")
    org_id = _get_org_id(current_user)
    period = db.query(PayrollPeriod).filter(PayrollPeriod.uuid == period_uuid, PayrollPeriod.organization_id == org_id).first()
    if not period: raise HTTPException(404, "Period not found")
    
    if period.status != PayrollStatus.PENDING_APPROVAL:
        raise HTTPException(400, "Only pending approval periods can be approved")
    
    before_state = PayrollAuditService.get_model_dict(period)
    period.status = PayrollStatus.APPROVED
    period.approved_at = func.now()
    period.approval_comments = data.comments
    if not isinstance(current_user, Organization):
        period.approved_by = current_user.id
    
    db.commit()
    db.refresh(period)

    PayrollAuditService.log(
        db=db,
        current_user=current_user,
        action_type="period_approved",
        entity_type="payroll_period",
        entity_id=period.id,
        before_state=before_state,
        after_state=PayrollAuditService.get_model_dict(period),
        risk_level="high",
        change_summary=f"Approved payroll period {period.period_name}"
    )
    return {"success": True, "message": "Payroll approved successfully", "data": PayrollPeriodSchema.model_validate(period)}

@router.post("/{period_uuid}/publish", response_model=PayrollPeriodResponse)
def publish_payroll(
    period_uuid: uuid.UUID, 
    db: Session = Depends(deps.get_db), 
    current_user: Union[Organization, Employee] = Depends(deps.get_current_user)
):
    _require_permission(db, current_user, PayrollPeriodPermissions.PROCESS, "publish payroll")
    org_id = _get_org_id(current_user)
    period = db.query(PayrollPeriod).filter(PayrollPeriod.uuid == period_uuid, PayrollPeriod.organization_id == org_id).first()
    if not period: raise HTTPException(404, "Period not found")
    
    if period.status != PayrollStatus.APPROVED:
        raise HTTPException(400, f"Only approved periods can be published. Current status: {period.status}")
    
    before_state = PayrollAuditService.get_model_dict(period)
    period.status = PayrollStatus.PUBLISHED
    period.published_at = func.now()
    if not isinstance(current_user, Organization):
        period.published_by = current_user.id
        
    db.query(Payslip).filter(
        Payslip.payroll_period_id == period.id,
        Payslip.organization_id == org_id
    ).update({
        Payslip.is_published: True,
        Payslip.published_at: func.now(),
        Payslip.status: PayslipStatus.PUBLISHED
    }, synchronize_session=False)
    
    db.commit()
    db.refresh(period)

    PayrollAuditService.log(
        db=db,
        current_user=current_user,
        action_type="period_published",
        entity_type="payroll_period",
        entity_id=period.id,
        before_state=before_state,
        after_state=PayrollAuditService.get_model_dict(period),
        risk_level="high",
        change_summary=f"Published payroll period {period.period_name} payslips to employees"
    )
    return {"success": True, "message": "Payroll published successfully", "data": PayrollPeriodSchema.model_validate(period)}

@router.post("/{period_uuid}/lock", response_model=PayrollPeriodResponse)
def lock_period(
    period_uuid: uuid.UUID, 
    db: Session = Depends(deps.get_db), 
    current_user: Union[Organization, Employee] = Depends(deps.get_current_user)
):
    _require_permission(db, current_user, PayrollPeriodPermissions.PROCESS, "lock period")
    org_id = _get_org_id(current_user)
    period = db.query(PayrollPeriod).filter(PayrollPeriod.uuid == period_uuid, PayrollPeriod.organization_id == org_id).first()
    if not period: raise HTTPException(404, "Period not found")
    
    if period.is_locked:
        raise HTTPException(status_code=400, detail="Period is already locked")

    before_state = PayrollAuditService.get_model_dict(period)
    period.is_locked = True
    period.locked_at = func.now()
    if not isinstance(current_user, Organization):
        period.locked_by = current_user.id
    
    db.commit()
    db.refresh(period)

    PayrollAuditService.log(
        db=db,
        current_user=current_user,
        action_type="period_locked",
        entity_type="payroll_period",
        entity_id=period.id,
        before_state=before_state,
        after_state=PayrollAuditService.get_model_dict(period),
        risk_level="high",
        change_summary=f"Locked payroll period {period.period_name} against further edits"
    )
    return {"success": True, "message": "Period locked successfully", "data": PayrollPeriodSchema.model_validate(period)}

@router.post("/{period_uuid}/unlock", response_model=PayrollPeriodResponse)
def unlock_period(
    period_uuid: uuid.UUID, 
    db: Session = Depends(deps.get_db), 
    current_user: Union[Organization, Employee] = Depends(deps.get_current_user)
):
    _require_permission(db, current_user, PayrollPeriodPermissions.PROCESS, "unlock period")
    org_id = _get_org_id(current_user)
    period = db.query(PayrollPeriod).filter(PayrollPeriod.uuid == period_uuid, PayrollPeriod.organization_id == org_id).first()
    if not period: raise HTTPException(404, "Period not found")
    if not period.is_locked:
        raise HTTPException(status_code=400, detail="Period is not locked")

    before_state = PayrollAuditService.get_model_dict(period)
    period.is_locked = False
    
    db.commit()
    db.refresh(period)

    PayrollAuditService.log(
        db=db,
        current_user=current_user,
        action_type="period_unlocked",
        entity_type="payroll_period",
        entity_id=period.id,
        before_state=before_state,
        after_state=PayrollAuditService.get_model_dict(period),
        risk_level="high",
        change_summary=f"Unlocked payroll period {period.period_name} for edits"
    )
    return {"success": True, "message": "Period unlocked successfully", "data": PayrollPeriodSchema.model_validate(period)}

@router.post("/{period_uuid}/hold", response_model=PayrollPeriodResponse)
def hold_period(
    period_uuid: uuid.UUID, 
    data: PayrollPeriodAction,
    db: Session = Depends(deps.get_db), 
    current_user: Union[Organization, Employee] = Depends(deps.get_current_user)
):
    _require_permission(db, current_user, PayrollPeriodPermissions.PROCESS, "hold period")
    org_id = _get_org_id(current_user)
    period = db.query(PayrollPeriod).filter(PayrollPeriod.uuid == period_uuid, PayrollPeriod.organization_id == org_id).first()
    if not period: raise HTTPException(404, "Period not found")
    
    before_state = PayrollAuditService.get_model_dict(period)
    period.status = PayrollStatus.ON_HOLD
    period.is_on_hold = True
    period.hold_reason = data.reason or data.comments
    
    db.commit()
    db.refresh(period)

    PayrollAuditService.log(
        db=db,
        current_user=current_user,
        action_type="period_held",
        entity_type="payroll_period",
        entity_id=period.id,
        before_state=before_state,
        after_state=PayrollAuditService.get_model_dict(period),
        risk_level="high",
        change_summary=f"Put payroll period {period.period_name} on hold"
    )
    return {"success": True, "message": "Payroll period put on hold", "data": PayrollPeriodSchema.model_validate(period)}

@router.post("/{period_uuid}/reverse", response_model=PayrollPeriodResponse)
def reverse_period(
    period_uuid: uuid.UUID, 
    data: PayrollPeriodAction,
    db: Session = Depends(deps.get_db), 
    current_user: Union[Organization, Employee] = Depends(deps.get_current_user)
):
    _require_permission(db, current_user, PayrollPeriodPermissions.PROCESS, "reverse period")
    org_id = _get_org_id(current_user)
    period = db.query(PayrollPeriod).filter(PayrollPeriod.uuid == period_uuid, PayrollPeriod.organization_id == org_id).first()
    if not period: raise HTTPException(404, "Period not found")
    
    if period.status in [PayrollStatus.DRAFT, PayrollStatus.REVERSED]:
        raise HTTPException(status_code=400, detail="Cannot reverse this period")

    before_state = PayrollAuditService.get_model_dict(period)
    period.status = PayrollStatus.REVERSED
    period.reversal_reason = data.reason or data.comments
    
    db.query(Payslip).filter(
        Payslip.payroll_period_id == period.id,
        Payslip.organization_id == org_id
    ).update({
        Payslip.status: PayslipStatus.REVERSED
    }, synchronize_session=False)
    
    db.commit()
    db.refresh(period)

    PayrollAuditService.log(
        db=db,
        current_user=current_user,
        action_type="period_reversed",
        entity_type="payroll_period",
        entity_id=period.id,
        before_state=before_state,
        after_state=PayrollAuditService.get_model_dict(period),
        risk_level="high",
        change_summary=f"Reversed payroll period {period.period_name} and all associated payslips"
    )
    return {"success": True, "message": "Payroll period and related payslips reversed successfully", "data": PayrollPeriodSchema.model_validate(period)}