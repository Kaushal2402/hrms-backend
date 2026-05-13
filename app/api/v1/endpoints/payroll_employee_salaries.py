import uuid
from typing import List, Optional, Union
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import func, and_, or_
from datetime import date, timedelta
from decimal import Decimal

from app.api import deps
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
        
    # Field mapping for friendly names/relationships
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
                # Ensure it's an instrumented attribute (column), not a relationship
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
    
    # Use joinedload to eager load related objects for enrichment
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
    db: Session = Depends(deps.get_db),
    current_user: Union[Organization, Employee] = Depends(deps.get_current_user)
):
    _require_permission(db, current_user, "107", "update")
    salary = db.query(EmployeeSalary).filter(EmployeeSalary.uuid == salary_uuid, EmployeeSalary.organization_id == _get_org_id(current_user)).first()
    if not salary or salary.is_on_hold: raise HTTPException(400, "Invalid request")
    salary.is_on_hold = True
    salary.hold_reason = hold_in.hold_reason
    salary.hold_from_date = hold_in.hold_from_date
    db.commit()
    return {"success": True, "message": "Employee salary has been put on hold successfully", "data": salary}

@router.patch("/{salary_uuid}/release", response_model=EmployeeSalaryResponse)
def release_salary(
    salary_uuid: uuid.UUID,
    db: Session = Depends(deps.get_db),
    current_user: Union[Organization, Employee] = Depends(deps.get_current_user)
):
    _require_permission(db, current_user, "107", "update")
    salary = db.query(EmployeeSalary).filter(EmployeeSalary.uuid == salary_uuid, EmployeeSalary.organization_id == _get_org_id(current_user)).first()
    if not salary or not salary.is_on_hold: raise HTTPException(400, "Salary is not on hold")
    salary.is_on_hold = False
    salary.hold_reason = None
    salary.hold_from_date = None
    db.commit()
    return {"success": True, "message": "Employee salary hold released successfully", "data": salary}

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
    
    # Mock breakdown logic (ideally should fetch components from db)
    breakdown = [
        {"component_name": "Basic Salary", "monthly": salary.monthly_ctc * Decimal("0.5"), "annual": salary.annual_ctc * Decimal("0.5")},
        {"component_name": "HRA", "monthly": salary.monthly_ctc * Decimal("0.2"), "annual": salary.annual_ctc * Decimal("0.2")},
        {"component_name": "Special Allowance", "monthly": salary.monthly_ctc * Decimal("0.3"), "annual": salary.annual_ctc * Decimal("0.3")}
    ]
    return {"success": True, "message": "CTC breakdown calculated successfully", "data": breakdown}