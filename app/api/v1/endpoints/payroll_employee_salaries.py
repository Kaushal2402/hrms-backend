import uuid
from typing import List, Optional, Union
from fastapi import APIRouter, Depends, HTTPException, Query, status, Request
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import func, and_, or_
from datetime import date, timedelta
from decimal import Decimal

from app.api import deps
from app.utils.payroll_audit import PayrollAuditService
from app.models.organization import Organization
from app.models.employee import Employee
from app.models.payroll import EmployeeSalary, SalaryTemplate, SalaryComponent
from app.schemas.payroll_employee_salaries import (
    EmployeeSalaryCreate, EmployeeSalaryUpdate, SalaryHoldUpdate, 
    SalaryRevisionCreate, EmployeeSalaryResponse, EmployeeSalaryListResponse,
    CTCBreakdownResponse
)

router = APIRouter()

def _get_org_id(current_user: Union[Organization, Employee]) -> int:
    return current_user.id if isinstance(current_user, Organization) else current_user.organization_id

def _require_permission(db, current_user, code, action_label):
    if isinstance(current_user, Organization): return
    if not deps.has_permission(db, current_user, code):
        raise HTTPException(status_code=403, detail=f"Permission denied: {action_label}")

def _apply_sorting(query, model, sort_by: str, sort_order: str):
    if not sort_by:
        return query.order_by(model.created_at.desc())
        
    MAPPING = {
        "employee": Employee.first_name,
        "salary_template": SalaryTemplate.template_name,
        "template": SalaryTemplate.template_name
    }
        
    try:
        for field in sort_by.split(","):
            field = field.strip()
            if field in MAPPING:
                col = MAPPING[field]
                query = query.order_by(col.desc() if sort_order == "desc" else col.asc())
            elif hasattr(model, field):
                col = getattr(model, field)
                if hasattr(col, "asc"):
                    query = query.order_by(col.desc() if sort_order == "desc" else col.asc())
        return query
    except Exception:
        return query.order_by(model.created_at.desc())

@router.get("/", response_model=EmployeeSalaryListResponse)
def get_employee_salaries(
    page: int = Query(1, ge=1),
    limit: int = Query(10, ge=1, le=100),
    employee_uuid: Optional[uuid.UUID] = None,
    is_active: Optional[bool] = None,
    search: Optional[str] = Query(None),
    sort_by: str = Query("effective_from"),
    sort_order: str = Query("desc"),
    db: Session = Depends(deps.get_db),
    current_user: Union[Organization, Employee] = Depends(deps.get_current_user)
):
    _require_permission(db, current_user, "105", "read")
    org_id = _get_org_id(current_user)
    
    query = db.query(EmployeeSalary).options(
        joinedload(EmployeeSalary.employee),
        joinedload(EmployeeSalary.salary_template)
    ).join(Employee, EmployeeSalary.employee_id == Employee.id).filter(EmployeeSalary.organization_id == org_id)
    
    if employee_uuid:
        query = query.filter(Employee.uuid == employee_uuid)
    
    if is_active is not None:
        query = query.filter(EmployeeSalary.is_active == is_active)
        
    if search:
        search_filter = f"%{search}%"
        query = query.filter(
            or_(
                Employee.first_name.ilike(search_filter),
                Employee.last_name.ilike(search_filter),
                Employee.employee_code.ilike(search_filter),
                EmployeeSalary.revision_reason.ilike(search_filter)
            )
        )
        
    query = _apply_sorting(query, EmployeeSalary, sort_by, sort_order)
    
    total = query.count()
    items = query.offset((page - 1) * limit).limit(limit).all()
    
    return EmployeeSalaryListResponse(
        success=True, 
        message="Employee salary records retrieved successfully", 
        data=items, 
        pagination={"total_records": total, "current_page": page, "total_pages": (total + limit - 1) // limit, "page_size": limit}
    )

@router.get("/lookup", response_model=EmployeeSalaryListResponse)
def lookup_employee_salaries(
    page: int = Query(1, ge=1),
    limit: int = Query(50, ge=1, le=100),
    search: Optional[str] = Query(None),
    is_active: Optional[bool] = Query(True),
    db: Session = Depends(deps.get_db),
    current_user: Union[Organization, Employee] = Depends(deps.get_current_user)
):
    org_id = _get_org_id(current_user)
    query = db.query(EmployeeSalary).options(
        joinedload(EmployeeSalary.employee)
    ).join(Employee).filter(EmployeeSalary.organization_id == org_id)
    
    if is_active is not None:
        query = query.filter(EmployeeSalary.is_active == is_active)
        
    if search:
        search_filter = f"%{search}%"
        query = query.filter(
            or_(
                Employee.first_name.ilike(search_filter),
                Employee.last_name.ilike(search_filter),
                Employee.employee_code.ilike(search_filter)
            )
        )
        
    total = query.count()
    items = query.offset((page - 1) * limit).limit(limit).all()
    return EmployeeSalaryListResponse(
        success=True, 
        message="Employee salary lookup retrieved successfully", 
        data=items, 
        pagination={"total_records": total, "current_page": page, "total_pages": (total + limit - 1) // limit, "page_size": limit}
    )

@router.post("/", response_model=EmployeeSalaryResponse)
def create_salary(
    item_in: EmployeeSalaryCreate,
    request: Request,
    db: Session = Depends(deps.get_db),
    current_user: Union[Organization, Employee] = Depends(deps.get_current_user)
):
    _require_permission(db, current_user, "106", "create")
    org_id = _get_org_id(current_user)
    emp = db.query(Employee).filter(Employee.uuid == item_in.employee_uuid, Employee.organization_id == org_id).first()
    if not emp: raise HTTPException(404, "Employee not found")
    
    template_id = None
    if item_in.template_uuid:
        tmpl = db.query(SalaryTemplate).filter(SalaryTemplate.uuid == item_in.template_uuid, SalaryTemplate.organization_id == org_id).first()
        if tmpl: template_id = tmpl.id

    # Deactivate existing
    db.query(EmployeeSalary).filter(EmployeeSalary.employee_id == emp.id, EmployeeSalary.is_active == True).update({"is_active": False})

    new_salary = EmployeeSalary(
        organization_id=org_id, 
        employee_id=emp.id, 
        template_id=template_id,
        annual_ctc=item_in.annual_ctc,
        monthly_ctc=item_in.annual_ctc / 12,
        monthly_gross=item_in.annual_ctc / 12, 
        monthly_net=item_in.annual_ctc / 12,   
        pay_frequency=item_in.pay_frequency,
        effective_from=item_in.effective_from,
        is_active=True
    )
    db.add(new_salary)
    db.commit()
    db.refresh(new_salary)

    # Audit Log
    PayrollAuditService.log(
        db=db,
        current_user=current_user,
        action_type="salary_assigned",
        entity_type="employee_salary",
        entity_id=new_salary.id,
        employee_id=emp.id,
        after_state=PayrollAuditService.get_model_dict(new_salary),
        change_summary=f"Assigned salary to {emp.first_name} {emp.last_name}",
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent")
    )
    db.commit()

    return {"success": True, "message": "Salary structure assigned to employee successfully", "data": new_salary}

@router.get("/{salary_uuid}", response_model=EmployeeSalaryResponse)
def get_salary_detail(
    salary_uuid: uuid.UUID,
    db: Session = Depends(deps.get_db),
    current_user: Union[Organization, Employee] = Depends(deps.get_current_user)
):
    _require_permission(db, current_user, "105", "read")
    salary = db.query(EmployeeSalary).options(
        joinedload(EmployeeSalary.employee),
        joinedload(EmployeeSalary.salary_template)
    ).filter(EmployeeSalary.uuid == salary_uuid, EmployeeSalary.organization_id == _get_org_id(current_user)).first()
    if not salary: raise HTTPException(404, "Salary record not found")
    return {"success": True, "message": "Salary details retrieved successfully", "data": salary}

@router.patch("/{salary_uuid}/hold", response_model=EmployeeSalaryResponse)
def hold_salary(
    salary_uuid: uuid.UUID,
    hold_in: SalaryHoldUpdate,
    request: Request,
    db: Session = Depends(deps.get_db),
    current_user: Union[Organization, Employee] = Depends(deps.get_current_user)
):
    _require_permission(db, current_user, "107", "update")
    salary = db.query(EmployeeSalary).filter(EmployeeSalary.uuid == salary_uuid, EmployeeSalary.organization_id == _get_org_id(current_user)).first()
    if not salary or salary.is_on_hold: raise HTTPException(400, "Invalid request")
    
    before_state = PayrollAuditService.get_model_dict(salary)
    
    salary.is_on_hold = True
    salary.hold_reason = hold_in.hold_reason
    salary.hold_from_date = hold_in.hold_from_date
    db.commit()
    db.refresh(salary)

    # Audit Log
    PayrollAuditService.log(
        db=db,
        current_user=current_user,
        action_type="salary_on_hold",
        entity_type="employee_salary",
        entity_id=salary.id,
        employee_id=salary.employee_id,
        before_state=before_state,
        after_state=PayrollAuditService.get_model_dict(salary),
        change_summary=f"Salary put on hold for {salary.employee.first_name}. Reason: {hold_in.hold_reason}",
        risk_level="medium",
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent")
    )
    db.commit()

    return {"success": True, "message": "Employee salary has been put on hold successfully", "data": salary}

@router.patch("/{salary_uuid}/release", response_model=EmployeeSalaryResponse)
def release_salary(
    salary_uuid: uuid.UUID,
    request: Request,
    db: Session = Depends(deps.get_db),
    current_user: Union[Organization, Employee] = Depends(deps.get_current_user)
):
    _require_permission(db, current_user, "107", "update")
    salary = db.query(EmployeeSalary).filter(EmployeeSalary.uuid == salary_uuid, EmployeeSalary.organization_id == _get_org_id(current_user)).first()
    if not salary or not salary.is_on_hold: raise HTTPException(400, "Salary is not on hold")
    
    before_state = PayrollAuditService.get_model_dict(salary)
    
    salary.is_on_hold = False
    salary.hold_reason = None
    salary.hold_from_date = None
    db.commit()
    db.refresh(salary)

    # Audit Log
    PayrollAuditService.log(
        db=db,
        current_user=current_user,
        action_type="salary_released",
        entity_type="employee_salary",
        entity_id=salary.id,
        employee_id=salary.employee_id,
        before_state=before_state,
        after_state=PayrollAuditService.get_model_dict(salary),
        change_summary=f"Salary released for {salary.employee.first_name}",
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent")
    )
    db.commit()

    return {"success": True, "message": "Employee salary hold released successfully", "data": salary}

@router.get("/employees/{employee_uuid}/salary", response_model=EmployeeSalaryResponse)
def get_current_salary(
    employee_uuid: uuid.UUID,
    db: Session = Depends(deps.get_db),
    current_user: Union[Organization, Employee] = Depends(deps.get_current_user)
):
    org_id = _get_org_id(current_user)
    emp = db.query(Employee).filter(Employee.uuid == employee_uuid, Employee.organization_id == org_id).first()
    if not emp:
        raise HTTPException(status_code=404, detail="Employee not found")
    
    salary = db.query(EmployeeSalary).options(
        joinedload(EmployeeSalary.employee),
        joinedload(EmployeeSalary.salary_template),
        joinedload(EmployeeSalary.bank_account)
    ).filter(
        EmployeeSalary.employee_id == emp.id, 
        EmployeeSalary.organization_id == org_id,
        EmployeeSalary.is_active == True
    ).first()
    
    if not salary:
        raise HTTPException(status_code=404, detail="No active salary record found for this employee")
        
    return {"success": True, "message": "Current salary retrieved successfully", "data": salary}

@router.post("/employees/{employee_uuid}/salary-revision", response_model=EmployeeSalaryResponse)
def create_salary_revision(
    employee_uuid: uuid.UUID,
    item_in: SalaryRevisionCreate,
    request: Request,
    db: Session = Depends(deps.get_db),
    current_user: Union[Organization, Employee] = Depends(deps.get_current_user)
):
    _require_permission(db, current_user, "107", "update")
    org_id = _get_org_id(current_user)
    
    emp = db.query(Employee).filter(Employee.uuid == employee_uuid, Employee.organization_id == org_id).first()
    if not emp:
        raise HTTPException(status_code=404, detail="Employee not found")
        
    current_salary = db.query(EmployeeSalary).filter(
        EmployeeSalary.employee_id == emp.id,
        EmployeeSalary.is_active == True
    ).first()
    
    template_id = None
    if item_in.template_uuid:
        tmpl = db.query(SalaryTemplate).filter(SalaryTemplate.uuid == item_in.template_uuid, SalaryTemplate.organization_id == org_id).first()
        if tmpl: template_id = tmpl.id
        
    bank_account_id = None
    if item_in.bank_account_uuid:
        from app.models.payroll import EmployeeBankAccount
        bank = db.query(EmployeeBankAccount).filter(EmployeeBankAccount.uuid == item_in.bank_account_uuid, EmployeeBankAccount.employee_id == emp.id).first()
        if bank: bank_account_id = bank.id

    # Capture before state if revising existing
    before_state = PayrollAuditService.get_model_dict(current_salary) if current_salary else None

    # Deactivate current
    if current_salary:
        current_salary.is_active = False
        current_salary.effective_to = item_in.effective_from - timedelta(days=1)
        
    # Create new revision
    new_salary = EmployeeSalary(
        organization_id=org_id,
        employee_id=emp.id,
        template_id=template_id,
        bank_account_id=bank_account_id,
        annual_ctc=item_in.annual_ctc,
        monthly_ctc=item_in.annual_ctc / 12,
        monthly_gross=item_in.annual_ctc / 12, 
        monthly_net=item_in.annual_ctc / 12,   
        pay_frequency=item_in.pay_frequency,
        currency=item_in.currency,
        payment_mode=item_in.payment_mode,
        effective_from=item_in.effective_from,
        revision_reason=item_in.revision_reason,
        previous_salary_id=current_salary.id if current_salary else None,
        revision_number=(current_salary.revision_number + 1) if current_salary else 1,
        is_active=True
    )
    
    db.add(new_salary)
    db.commit()
    db.refresh(new_salary)

    # Audit Log
    action = "salary_revised" if current_salary else "salary_assigned"
    PayrollAuditService.log(
        db=db,
        current_user=current_user,
        action_type=action,
        entity_type="employee_salary",
        entity_id=new_salary.id,
        employee_id=emp.id,
        before_state=before_state,
        after_state=PayrollAuditService.get_model_dict(new_salary),
        change_summary=f"Salary revision for {emp.first_name}. Reason: {item_in.revision_reason}",
        risk_level="high",
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent")
    )
    db.commit()
    
    return {"success": True, "message": "Salary revision created successfully", "data": new_salary}

@router.get("/employees/{employee_uuid}/ctc-breakdown", response_model=CTCBreakdownResponse)
def get_ctc_breakdown(
    employee_uuid: uuid.UUID,
    db: Session = Depends(deps.get_db),
    current_user: Union[Organization, Employee] = Depends(deps.get_current_user)
):
    org_id = _get_org_id(current_user)
    emp = db.query(Employee).filter(Employee.uuid == employee_uuid, Employee.organization_id == org_id).first()
    if not emp: raise HTTPException(404, "Employee not found")
    
    salary = db.query(EmployeeSalary).filter(EmployeeSalary.employee_id == emp.id, EmployeeSalary.is_active == True).first()
    if not salary: raise HTTPException(404, "No active salary found")
    
    breakdown = [
        {"component_name": "Basic Salary", "monthly": salary.monthly_ctc * Decimal("0.5"), "annual": salary.annual_ctc * Decimal("0.5")},
        {"component_name": "HRA", "monthly": salary.monthly_ctc * Decimal("0.2"), "annual": salary.annual_ctc * Decimal("0.2")},
        {"component_name": "Special Allowance", "monthly": salary.monthly_ctc * Decimal("0.3"), "annual": salary.annual_ctc * Decimal("0.3")}
    ]
    return {"success": True, "message": "CTC breakdown calculated successfully", "data": breakdown}