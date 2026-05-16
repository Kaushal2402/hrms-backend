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
    item = db.query(PayrollPeriod).filter(PayrollPeriod.uuid == period_uuid, PayrollPeriod.organization_id == _get_org_id(current_user)).first()
    if not item or item.is_locked: raise HTTPException(400, "Period not found or locked")
    for f, v in item_in.model_dump(exclude_unset=True).items(): setattr(item, f, v)
    db.commit(); db.refresh(item)
    return {"success": True, "message": "Updated successfully", "data": item}

@router.post("/{period_uuid}/process", response_model=PayrollPeriodResponse)
def process_payroll(
    period_uuid: uuid.UUID, 
    data: PayrollPeriodAction,
    db: Session = Depends(deps.get_db), 
    current_user: Union[Organization, Employee] = Depends(deps.get_current_user)
):
    _require_permission(db, current_user, PayrollPeriodPermissions.PROCESS, "process")
    org_id = _get_org_id(current_user)
    item = db.query(PayrollPeriod).filter(PayrollPeriod.uuid == period_uuid, PayrollPeriod.organization_id == org_id).first()
    if not item: raise HTTPException(404, "Period not found")
    
    if item.status.value != PayrollStatus.APPROVED.value:
        raise HTTPException(400, f"Only approved periods can be processed. Current status: {item.status}")
    
    # 1. Clear existing payslips for re-processing (if not already paid/published)
    db.query(PayslipComponent).filter(
        PayslipComponent.payslip_id.in_(
            db.query(Payslip.id).filter(Payslip.payroll_period_id == item.id)
        )
    ).delete(synchronize_session=False)
    db.query(Payslip).filter(Payslip.payroll_period_id == item.id).delete(synchronize_session=False)
    
    # 2. Fetch all eligible employees (active with assigned salary)
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
        # Create Payslip
        payslip = Payslip(
            organization_id=org_id,
            payroll_period_id=item.id,
            employee_id=salary.employee_id,
            employee_salary_id=salary.id,
            payslip_number=f"PS-{org_id}-{item.period_code}-{salary.employee_id}-{uuid.uuid4().hex[:4]}",
            period_start_date=item.period_start_date,
            period_end_date=item.period_end_date,
            payment_date=item.payment_date,
            total_working_days=item.total_working_days,
            paid_days=item.total_working_days, # Default to full pay, can be refined later
            days_present=item.total_working_days,
            basic_salary=salary.monthly_gross * Decimal("0.5"), # Simple mock logic for basic
            gross_salary=salary.monthly_gross,
            total_earnings=salary.monthly_gross,
            total_deductions=salary.monthly_gross - salary.monthly_net,
            net_salary=salary.monthly_net,
            monthly_ctc=salary.monthly_ctc,
            status=PayslipStatus.GENERATED,
            is_published=False
        )
        db.add(payslip)
        db.flush() # Get payslip.id
        
        # Add Components
        comp_query = db.query(EmployeeSalaryComponent).filter(EmployeeSalaryComponent.employee_salary_id == salary.id)
        for esc in comp_query.all():
            ps_comp = PayslipComponent(
                payslip_id=payslip.id,
                component_id=esc.component_id,
                component_name="Component", # In real app, join with SalaryComponent
                component_type=ComponentType.EARNING, # Simplified
                monthly_amount=esc.monthly_amount,
                actual_amount=esc.monthly_amount
            )
            db.add(ps_comp)
            
        total_gross += salary.monthly_gross
        total_deductions += (salary.monthly_gross - salary.monthly_net)
        total_net += salary.monthly_net
        total_employer_contrib += (salary.monthly_ctc - salary.monthly_gross)
        headcount += 1
        
    # 4. Update Period Totals
    item.total_employees = headcount
    item.total_gross_amount = total_gross
    item.total_deductions = total_deductions
    item.total_net_amount = total_net
    item.total_employer_contributions = total_employer_contrib
    
    item.status = PayrollStatus.PROCESSED
    item.processing_completed_at = func.now()
    if not isinstance(current_user, Organization):
        item.processed_by = current_user.id
    
    db.commit()
    db.refresh(item)
    return {"success": True, "message": f"Payroll processed successfully. {headcount} payslips generated.", "data": item}

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
    
    if item.status not in [PayrollStatus.DRAFT, PayrollStatus.IN_PROGRESS, PayrollStatus.ON_HOLD]:
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
    
    if item.status.value != PayrollStatus.PROCESSED.value:
        raise HTTPException(400, f"Only processed periods can be published. Current status: {item.status}")
    
    item.status = PayrollStatus.PUBLISHED
    item.published_at = func.now()
    if not isinstance(current_user, Organization):
        item.published_by = current_user.id
        
    # Bulk update payslips
    db.query(Payslip).filter(
        Payslip.payroll_period_id == item.id,
        Payslip.organization_id == org_id
    ).update({
        Payslip.is_published: True,
        Payslip.published_at: func.now(),
        Payslip.status: PayslipStatus.PUBLISHED
    }, synchronize_session=False)
    
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