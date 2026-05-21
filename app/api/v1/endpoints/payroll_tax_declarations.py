import uuid
from typing import List, Optional, Union
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import func, and_

from app.api import deps
from app.models.organization import Organization
from app.models.employee import Employee
from app.models.payroll import TaxDeclaration, TaxDeclarationItem, TaxCalculation, TaxRegime, EmployeeSalary
from app.schemas.payroll_tax_declarations import (
    TaxDeclarationSchema, TaxDeclarationCreate, TaxDeclarationUpdate,
    TaxDeclarationListResponse, TaxDeclarationResponse, TaxDeclarationItemCreate,
    TaxDeclarationItemApproval, TaxCalculationSchema, TaxCalculationResponse,
    TaxRegimeComparisonSchema, CalculateTaxRequest, BulkTaxCalculationRequest,
    BulkTaxCalculationResponse, TaxRegimeComparisonResponse
)

router = APIRouter()

class PayrollTaxPermissions:
    READ = "122"
    CREATE = "123"
    APPROVE = "124"

def _get_org_id(current_user: Union[Organization, Employee]) -> int:
    return current_user.id if isinstance(current_user, Organization) else current_user.organization_id

def _require_permission(db, current_user, code, action_label):
    if isinstance(current_user, Organization): return
    if not deps.has_permission(db, current_user, code):
        raise HTTPException(status_code=403, detail=f"Permission denied: {action_label}")

@router.get("/", response_model=TaxDeclarationListResponse)
def get_tax_declarations(
    page: int = Query(1, ge=1), limit: int = Query(10, ge=1, le=100),
    employee_id: Optional[uuid.UUID] = None, financial_year: Optional[str] = None,
    status: Optional[str] = None, min_amount: Optional[float] = None,
    sort_by: str = Query("created_at"), order: str = Query("desc"),
    db: Session = Depends(deps.get_db),
    current_user: Union[Organization, Employee] = Depends(deps.get_current_user)
):
    org_id = _get_org_id(current_user)
    is_org = isinstance(current_user, Organization)
    if not is_org:
        has_perm = deps.has_permission(db, current_user, PayrollTaxPermissions.READ)
        if not has_perm:
            employee_id = current_user.uuid
            
    query = db.query(TaxDeclaration).filter(TaxDeclaration.organization_id == org_id)
    
    # Eager load the employee object and its relations
    query = query.options(
        joinedload(TaxDeclaration.employee).joinedload(Employee.department),
        joinedload(TaxDeclaration.employee).joinedload(Employee.job_title)
    )
    
    if employee_id: query = query.join(Employee, TaxDeclaration.employee_id == Employee.id).filter(Employee.uuid == employee_id)
    if financial_year: query = query.filter(TaxDeclaration.financial_year == financial_year)
    if status: query = query.filter(TaxDeclaration.status == status)
    if min_amount: query = query.filter(TaxDeclaration.total_declared_amount >= min_amount)
    
    # Apply advanced sorting
    if sort_by == "employee_name":
        if not employee_id:
            query = query.outerjoin(Employee, TaxDeclaration.employee_id == Employee.id)
        if order.lower() == "asc":
            query = query.order_by(Employee.first_name.asc(), Employee.last_name.asc())
        else:
            query = query.order_by(Employee.first_name.desc(), Employee.last_name.desc())
    elif sort_by == "total_declared_amount":
        if order.lower() == "asc":
            query = query.order_by(TaxDeclaration.total_declared_amount.asc())
        else:
            query = query.order_by(TaxDeclaration.total_declared_amount.desc())
    elif sort_by == "total_approved_amount":
        if order.lower() == "asc":
            query = query.order_by(TaxDeclaration.total_approved_amount.asc())
        else:
            query = query.order_by(TaxDeclaration.total_approved_amount.desc())
    elif sort_by == "status":
        if order.lower() == "asc":
            query = query.order_by(TaxDeclaration.status.asc())
        else:
            query = query.order_by(TaxDeclaration.status.desc())
    else: # default created_at
        if order.lower() == "asc":
            query = query.order_by(TaxDeclaration.created_at.asc())
        else:
            query = query.order_by(TaxDeclaration.created_at.desc())
    
    total = query.count()
    items = query.offset((page - 1) * limit).limit(limit).all()
    
    from sqlalchemy import func
    summary_res = db.query(
        func.coalesce(func.sum(TaxDeclaration.total_declared_amount), 0),
        func.coalesce(func.sum(TaxDeclaration.total_approved_amount), 0),
        func.count(TaxDeclaration.id)
    ).filter(
        TaxDeclaration.organization_id == org_id
    )
    if employee_id:
        summary_res = summary_res.join(Employee, TaxDeclaration.employee_id == Employee.id).filter(Employee.uuid == employee_id)
    if financial_year:
        summary_res = summary_res.filter(TaxDeclaration.financial_year == financial_year)
    if status:
        summary_res = summary_res.filter(TaxDeclaration.status == status)
    if min_amount:
        summary_res = summary_res.filter(TaxDeclaration.total_declared_amount >= min_amount)
        
    sum_decl, sum_app, count_active = summary_res.first() or (0, 0, 0)
    
    summary = {
        "total_declared_amount": sum_decl,
        "total_approved_amount": sum_app,
        "active_declarations": count_active
    }
    
    return TaxDeclarationListResponse(
        success=True,
        message="Tax declarations retrieved successfully",
        data=items,
        pagination={
            "total_records": total,
            "current_page": page,
            "total_pages": (total + limit - 1) // limit,
            "page_size": limit
        },
        summary=summary
    )

@router.post("/", response_model=TaxDeclarationResponse)
def create_tax_declaration(item_in: TaxDeclarationCreate, db: Session = Depends(deps.get_db), current_user: Union[Organization, Employee] = Depends(deps.get_current_user)):
    org_id = _get_org_id(current_user)
    emp = db.query(Employee).filter(Employee.uuid == item_in.employee_uuid, Employee.organization_id == org_id).first()
    if not emp: raise HTTPException(404, "Employee not found")
    
    is_org = isinstance(current_user, Organization)
    if not is_org:
        has_perm = deps.has_permission(db, current_user, PayrollTaxPermissions.CREATE)
        is_own = emp.id == current_user.id
        if not has_perm and not is_own:
            raise HTTPException(status_code=403, detail="Permission denied")
            
    if db.query(TaxDeclaration).filter(TaxDeclaration.employee_id == emp.id, TaxDeclaration.financial_year == item_in.financial_year).first():
         raise HTTPException(400, "Declaration already exists for this year")
    decl = TaxDeclaration(organization_id=org_id, employee_id=emp.id, **item_in.model_dump(exclude={'employee_uuid'}))
    db.add(decl); db.commit(); db.refresh(decl)
    return {"success": True, "message": "Tax declaration created successfully", "data": decl}

@router.get("/{declaration_uuid}", response_model=TaxDeclarationResponse)
def get_declaration(declaration_uuid: uuid.UUID, db: Session = Depends(deps.get_db), current_user: Union[Organization, Employee] = Depends(deps.get_current_user)):
    org_id = _get_org_id(current_user)
    decl = db.query(TaxDeclaration).filter(
        TaxDeclaration.uuid == declaration_uuid,
        TaxDeclaration.organization_id == org_id
    ).options(
        joinedload(TaxDeclaration.items),
        joinedload(TaxDeclaration.employee).joinedload(Employee.department),
        joinedload(TaxDeclaration.employee).joinedload(Employee.job_title)
    ).first()
    if not decl: raise HTTPException(404, "Declaration not found")
    
    is_org = isinstance(current_user, Organization)
    if not is_org:
        has_perm = deps.has_permission(db, current_user, PayrollTaxPermissions.READ)
        is_own = decl.employee_id == current_user.id
        if not has_perm and not is_own:
            raise HTTPException(status_code=403, detail="Permission denied")
            
    return {"success": True, "message": "Tax declaration retrieved successfully", "data": decl}

def _update_declaration_totals(db: Session, decl: TaxDeclaration):
    declared_sum = sum(item.declared_amount for item in decl.items)
    approved_sum = sum(item.approved_amount for item in decl.items if item.is_verified and not item.is_rejected and item.approved_amount is not None)
    decl.total_declared_amount = declared_sum
    decl.total_approved_amount = approved_sum
    db.add(decl)
    db.commit()

@router.post("/{declaration_uuid}/items", response_model=TaxDeclarationResponse)
def add_items(declaration_uuid: uuid.UUID, items: List[TaxDeclarationItemCreate], db: Session = Depends(deps.get_db), current_user: Union[Organization, Employee] = Depends(deps.get_current_user)):
    org_id = _get_org_id(current_user)
    decl = db.query(TaxDeclaration).filter(TaxDeclaration.uuid == declaration_uuid, TaxDeclaration.organization_id == org_id).first()
    if not decl or decl.is_locked: raise HTTPException(400, "Declaration not found or locked")
    
    is_org = isinstance(current_user, Organization)
    if not is_org:
        has_perm = deps.has_permission(db, current_user, PayrollTaxPermissions.CREATE)
        is_own = decl.employee_id == current_user.id
        if not has_perm and not is_own:
            raise HTTPException(status_code=403, detail="Permission denied")
            
    try:
        for item in items:
            db.add(TaxDeclarationItem(tax_declaration_id=decl.id, **item.model_dump()))
        db.commit()
        db.refresh(decl)
        _update_declaration_totals(db, decl)
        db.refresh(decl)
    except Exception:
        db.rollback(); raise HTTPException(500, "Failed to add items")
    return {"success": True, "message": "Items added successfully", "data": decl}

@router.put("/{declaration_uuid}/items/{item_uuid}", response_model=TaxDeclarationResponse)
def update_item(
    declaration_uuid: uuid.UUID,
    item_uuid: uuid.UUID,
    item_in: TaxDeclarationItemCreate,
    db: Session = Depends(deps.get_db),
    current_user: Union[Organization, Employee] = Depends(deps.get_current_user)
):
    org_id = _get_org_id(current_user)
    decl = db.query(TaxDeclaration).filter(
        TaxDeclaration.uuid == declaration_uuid,
        TaxDeclaration.organization_id == org_id
    ).first()
    if not decl or decl.is_locked:
        raise HTTPException(400, "Declaration not found or locked")
        
    is_org = isinstance(current_user, Organization)
    if not is_org:
        has_perm = deps.has_permission(db, current_user, PayrollTaxPermissions.CREATE)
        is_own = decl.employee_id == current_user.id
        if not has_perm and not is_own:
            raise HTTPException(status_code=403, detail="Permission denied")
            
    item = db.query(TaxDeclarationItem).filter(
        TaxDeclarationItem.uuid == item_uuid,
        TaxDeclarationItem.tax_declaration_id == decl.id
    ).first()
    if not item:
        raise HTTPException(404, "Item not found")
    
    update_data = item_in.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(item, field, value)
    
    db.commit()
    _update_declaration_totals(db, decl)
    db.refresh(decl)
    return {"success": True, "message": "Item updated successfully", "data": decl}

@router.delete("/{declaration_uuid}/items/{item_uuid}", response_model=TaxDeclarationResponse)
def delete_item(
    declaration_uuid: uuid.UUID,
    item_uuid: uuid.UUID,
    db: Session = Depends(deps.get_db),
    current_user: Union[Organization, Employee] = Depends(deps.get_current_user)
):
    org_id = _get_org_id(current_user)
    decl = db.query(TaxDeclaration).filter(
        TaxDeclaration.uuid == declaration_uuid,
        TaxDeclaration.organization_id == org_id
    ).first()
    if not decl or decl.is_locked:
        raise HTTPException(400, "Declaration not found or locked")
        
    is_org = isinstance(current_user, Organization)
    if not is_org:
        has_perm = deps.has_permission(db, current_user, PayrollTaxPermissions.CREATE)
        is_own = decl.employee_id == current_user.id
        if not has_perm and not is_own:
            raise HTTPException(status_code=403, detail="Permission denied")
            
    item = db.query(TaxDeclarationItem).filter(
        TaxDeclarationItem.uuid == item_uuid,
        TaxDeclarationItem.tax_declaration_id == decl.id
    ).first()
    if not item:
        raise HTTPException(404, "Item not found")
    
    db.delete(item)
    db.commit()
    _update_declaration_totals(db, decl)
    db.refresh(decl)
    return {"success": True, "message": "Item deleted successfully", "data": decl}

@router.post("/{declaration_uuid}/submit", response_model=TaxDeclarationResponse)
def submit_declaration(declaration_uuid: uuid.UUID, db: Session = Depends(deps.get_db), current_user: Union[Organization, Employee] = Depends(deps.get_current_user)):
    org_id = _get_org_id(current_user)
    decl = db.query(TaxDeclaration).filter(TaxDeclaration.uuid == declaration_uuid, TaxDeclaration.organization_id == org_id).first()
    if not decl or decl.is_locked: raise HTTPException(400, "Invalid state")
    
    is_org = isinstance(current_user, Organization)
    if not is_org:
        has_perm = deps.has_permission(db, current_user, PayrollTaxPermissions.CREATE)
        is_own = decl.employee_id == current_user.id
        if not has_perm and not is_own:
            raise HTTPException(status_code=403, detail="Permission denied")
            
    decl.status = "submitted"
    db.commit(); db.refresh(decl)
    return {"success": True, "message": "Declaration submitted successfully", "data": decl}

@router.post("/{declaration_uuid}/approve", response_model=TaxDeclarationResponse)
def approve_declaration(declaration_uuid: uuid.UUID, approvals: List[TaxDeclarationItemApproval], db: Session = Depends(deps.get_db), current_user: Union[Organization, Employee] = Depends(deps.get_current_user)):
    _require_permission(db, current_user, PayrollTaxPermissions.APPROVE, "approve")
    decl = db.query(TaxDeclaration).filter(TaxDeclaration.uuid == declaration_uuid, TaxDeclaration.organization_id == _get_org_id(current_user)).first()
    if not decl: raise HTTPException(404, "Not found")
    for app in approvals:
        item = db.query(TaxDeclarationItem).filter(TaxDeclarationItem.uuid == app.item_uuid, TaxDeclarationItem.tax_declaration_id == decl.id).first()
        if item:
            item.approved_amount = app.approved_amount
            item.is_verified = app.is_verified
            item.is_rejected = app.is_rejected
    decl.status = "approved"
    db.commit()
    _update_declaration_totals(db, decl)
    db.refresh(decl)
    return {"success": True, "message": "Declaration approved successfully", "data": decl}

@router.post("/{declaration_uuid}/lock", response_model=TaxDeclarationResponse)
def lock_declaration(declaration_uuid: uuid.UUID, db: Session = Depends(deps.get_db), current_user: Union[Organization, Employee] = Depends(deps.get_current_user)):
    decl = db.query(TaxDeclaration).filter(TaxDeclaration.uuid == declaration_uuid, TaxDeclaration.organization_id == _get_org_id(current_user)).first()
    if not decl: raise HTTPException(404, "Not found")
    decl.is_locked = True
    db.commit(); db.refresh(decl)
    return {"success": True, "message": "Declaration locked successfully", "data": decl}

@router.put("/{declaration_uuid}", response_model=TaxDeclarationResponse)
def update_declaration(
    declaration_uuid: uuid.UUID,
    item_in: TaxDeclarationUpdate,
    db: Session = Depends(deps.get_db),
    current_user: Union[Organization, Employee] = Depends(deps.get_current_user)
):
    org_id = _get_org_id(current_user)
    decl = db.query(TaxDeclaration).filter(
        TaxDeclaration.uuid == declaration_uuid,
        TaxDeclaration.organization_id == org_id
    ).first()
    if not decl:
        raise HTTPException(404, "Tax declaration not found")
    if decl.is_locked:
        raise HTTPException(400, "Tax declaration is locked and cannot be updated")
        
    is_org = isinstance(current_user, Organization)
    if not is_org:
        has_perm = deps.has_permission(db, current_user, PayrollTaxPermissions.CREATE)
        is_own = decl.employee_id == current_user.id
        if not has_perm and not is_own:
            raise HTTPException(status_code=403, detail="Permission denied")
            
    update_data = item_in.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(decl, field, value)
    
    db.commit()
    db.refresh(decl)
    return {"success": True, "message": "Tax declaration updated successfully", "data": decl}

def _calculate_tax_for_emp(
    db: Session,
    employee: Employee,
    org_id: int,
    financial_year: str,
    regime: TaxRegime,
    projections: Optional[dict] = None
) -> TaxCalculation:
    # 1. Determine gross annual income
    emp_salary = db.query(EmployeeSalary).filter(
        EmployeeSalary.employee_id == employee.id,
        EmployeeSalary.is_active == True
    ).first()
    
    gross_annual_income = 0.0
    if projections and "gross_annual_income" in projections:
        gross_annual_income = float(projections["gross_annual_income"])
    elif emp_salary:
        gross_annual_income = float(emp_salary.annual_ctc)
    else:
        gross_annual_income = 600000.0  # Fallback base
        
    # Add other projection income if present
    if projections:
        gross_annual_income += float(projections.get("bonus", 0.0))
        gross_annual_income += float(projections.get("other_income", 0.0))
        
    # 2. Get tax declarations for the financial year
    decl = db.query(TaxDeclaration).filter(
        TaxDeclaration.employee_id == employee.id,
        TaxDeclaration.financial_year == financial_year
    ).first()
    
    exemption_hra = 0.0
    exemption_lta = 0.0
    deduction_80c = 0.0
    deduction_80d = 0.0
    deduction_other = 0.0
    
    if decl:
        items = db.query(TaxDeclarationItem).filter(
            TaxDeclarationItem.tax_declaration_id == decl.id,
            TaxDeclarationItem.is_rejected == False
        ).all()
        for item in items:
            amt = float(item.approved_amount if item.is_verified and item.approved_amount is not None else item.declared_amount)
            sec = item.tax_section.upper()
            if '80C' in sec:
                deduction_80c += amt
            elif '80D' in sec:
                deduction_80d += amt
            elif 'HRA' in sec:
                exemption_hra += amt
            elif 'LTA' in sec:
                exemption_lta += amt
            else:
                deduction_other += amt

    # Capping rules for India (progressive)
    deduction_80c = min(deduction_80c, 150000.0)
    # 80D limit depends on regime
    if regime == TaxRegime.NEW:
        deduction_80d = 0.0
        
    # Standard deduction
    standard_ded = 75000.0 if regime == TaxRegime.NEW else 50000.0
    prof_tax = 2500.0
    
    # If regime is NEW, exemptions and sections like 80C/80D are not allowed
    if regime == TaxRegime.NEW:
        exemption_hra = 0.0
        exemption_lta = 0.0
        deduction_80c = 0.0
        deduction_80d = 0.0
        deduction_other = 0.0
        
    total_deductions = standard_ded + prof_tax + exemption_hra + exemption_lta + deduction_80c + deduction_80d + deduction_other
    taxable_income = max(0.0, gross_annual_income - total_deductions)
    
    # Tax calculation based on slabs
    tax_on_income = 0.0
    slab_breakdown = []
    
    if regime == TaxRegime.NEW:
        # New Regime Slabs (FY 2024-25):
        # Up to 3,00,000: Nil
        # 3,00,001 to 6,00,000: 5%
        # 6,00,001 to 9,00,000: 10%
        # 9,00,001 to 12,00,000: 15%
        # 12,00,001 to 15,00,000: 20%
        # Above 15,00,000: 30%
        slabs = [
            (300000.0, 0.0),
            (300000.0, 0.05),
            (300000.0, 0.10),
            (300000.0, 0.15),
            (300000.0, 0.20),
            (float('inf'), 0.30)
        ]
    else:
        # Old Regime Slabs (FY 2024-25):
        # Up to 2,50,000: Nil
        # 2,50,001 to 5,00,000: 5%
        # 5,00,001 to 10,00,000: 20%
        # Above 10,00,000: 30%
        slabs = [
            (250000.0, 0.0),
            (250000.0, 0.05),
            (500000.0, 0.20),
            (float('inf'), 0.30)
        ]
        
    temp_income = taxable_income
    for limit, rate in slabs:
        if temp_income <= 0:
            break
        taxable_part = min(temp_income, limit)
        tax_part = taxable_part * rate
        tax_on_income += tax_part
        slab_breakdown.append({
            "taxable_amount": taxable_part,
            "rate": rate,
            "tax_amount": tax_part
        })
        temp_income -= taxable_part
        
    # Rebate under 87A
    rebate = 0.0
    if regime == TaxRegime.NEW and taxable_income <= 700000.0:
        rebate = min(tax_on_income, 25000.0)
    elif regime == TaxRegime.OLD and taxable_income <= 500000.0:
        rebate = min(tax_on_income, 12500.0)
        
    tax_after_rebate = max(0.0, tax_on_income - rebate)
    
    # Surcharge (simplified: 10% if taxable income > 50L)
    surcharge = 0.0
    if taxable_income > 5000000.0:
        surcharge = tax_after_rebate * 0.10
        
    # Cess (4%)
    cess = (tax_after_rebate + surcharge) * 0.04
    total_tax = tax_after_rebate + surcharge + cess
    
    monthly_tds = total_tax / 12.0
    
    # Find or create TaxCalculation record
    calc = db.query(TaxCalculation).filter(
        TaxCalculation.employee_id == employee.id,
        TaxCalculation.financial_year == financial_year,
        TaxCalculation.tax_regime == regime
    ).first()
    
    if not calc:
        calc = TaxCalculation(
            organization_id=org_id,
            employee_id=employee.id,
            financial_year=financial_year,
            tax_regime=regime,
            calculation_type="projected"
        )
        db.add(calc)
        
    calc.gross_annual_income = gross_annual_income
    calc.standard_deduction = standard_ded
    calc.hra_exemption = exemption_hra
    calc.lta_exemption = exemption_lta
    calc.professional_tax = prof_tax
    calc.total_80c_deductions = deduction_80c
    calc.total_80d_deductions = deduction_80d
    calc.total_other_deductions = deduction_other
    calc.total_deductions = total_deductions
    calc.taxable_income = taxable_income
    calc.tax_on_income = tax_on_income
    calc.surcharge = surcharge
    calc.cess = cess
    calc.total_tax = total_tax
    calc.rebate_under_87a = rebate
    calc.net_tax_payable = total_tax
    calc.monthly_tds = monthly_tds
    calc.tax_slab_breakdown = slab_breakdown
    calc.deduction_breakdown = {
        "standard_deduction": standard_ded,
        "professional_tax": prof_tax,
        "80C": deduction_80c,
        "80D": deduction_80d,
        "HRA": exemption_hra,
        "LTA": exemption_lta,
        "other": deduction_other
    }
    
    db.commit()
    db.refresh(calc)
    return calc

@router.get("/employees/{employee_uuid}/tax-calculation", response_model=TaxCalculationResponse)
def get_tax_calc(
    employee_uuid: uuid.UUID,
    financial_year: str,
    db: Session = Depends(deps.get_db),
    current_user: Union[Organization, Employee] = Depends(deps.get_current_user)
):
    is_self = not isinstance(current_user, Organization) and current_user.uuid == employee_uuid
    if not is_self:
        _require_permission(db, current_user, PayrollTaxPermissions.READ, "view tax calculation")
    org_id = _get_org_id(current_user)
    calc = db.query(TaxCalculation).join(Employee, TaxCalculation.employee_id == Employee.id).filter(
        Employee.uuid == employee_uuid,
        Employee.organization_id == org_id,
        TaxCalculation.financial_year == financial_year
    ).first()
    if not calc:
        raise HTTPException(404, "Calculation not found")
    return {"success": True, "message": "Calculation retrieved", "data": calc}

@router.post("/employees/{employee_uuid}/calculate-tax", response_model=TaxCalculationResponse)
def calculate_employee_tax(
    employee_uuid: uuid.UUID,
    item_in: CalculateTaxRequest,
    db: Session = Depends(deps.get_db),
    current_user: Union[Organization, Employee] = Depends(deps.get_current_user)
):
    is_self = not isinstance(current_user, Organization) and current_user.uuid == employee_uuid
    if not is_self:
        _require_permission(db, current_user, PayrollTaxPermissions.CREATE, "calculate tax")
    org_id = _get_org_id(current_user)
    
    # Verify employee
    employee = db.query(Employee).filter(
        Employee.uuid == employee_uuid,
        Employee.organization_id == org_id
    ).first()
    if not employee:
        raise HTTPException(404, "Employee not found")
        
    # Determine tax regime
    regime = item_in.tax_regime
    if not regime or regime == TaxRegime.DEFAULT:
        decl = db.query(TaxDeclaration).filter(
            TaxDeclaration.employee_id == employee.id,
            TaxDeclaration.financial_year == item_in.financial_year
        ).first()
        regime = decl.tax_regime if decl else TaxRegime.NEW
        
    calc = _calculate_tax_for_emp(
        db=db,
        employee=employee,
        org_id=org_id,
        financial_year=item_in.financial_year,
        regime=regime,
        projections=item_in.projections
    )
    
    return {"success": True, "message": "Tax calculated successfully", "data": calc}

@router.post("/tax-calculations/bulk", response_model=BulkTaxCalculationResponse)
def bulk_calculate_tax(
    item_in: BulkTaxCalculationRequest,
    db: Session = Depends(deps.get_db),
    current_user: Union[Organization, Employee] = Depends(deps.get_current_user)
):
    _require_permission(db, current_user, PayrollTaxPermissions.CREATE, "bulk calculate tax")
    org_id = _get_org_id(current_user)
    
    query = db.query(Employee).filter(
        Employee.organization_id == org_id,
        Employee.is_active == True
    )
    
    if item_in.employee_uuids:
        query = query.filter(Employee.uuid.in_(item_in.employee_uuids))
    
    if item_in.department_uuid:
        from app.models.department import Department
        query = query.join(Department).filter(Department.uuid == item_in.department_uuid)
        
    if item_in.location_uuid:
        from app.models.location import Location
        query = query.join(Location).filter(Location.uuid == item_in.location_uuid)
        
    employees = query.all()
    
    total_processed = 0
    for emp in employees:
        decl = db.query(TaxDeclaration).filter(
            TaxDeclaration.employee_id == emp.id,
            TaxDeclaration.financial_year == item_in.financial_year
        ).first()
        regime = decl.tax_regime if decl else TaxRegime.NEW
        
        try:
            _calculate_tax_for_emp(
                db=db,
                employee=emp,
                org_id=org_id,
                financial_year=item_in.financial_year,
                regime=regime
            )
            total_processed += 1
        except Exception as e:
            # Continue on error
            pass
            
    return {
        "success": True,
        "message": f"Bulk tax calculation completed for {total_processed} employees",
        "total_processed": total_processed
    }

@router.get("/employees/{employee_uuid}/tax-regime-comparison", response_model=TaxRegimeComparisonResponse)
def compare_tax_regimes(
    employee_uuid: uuid.UUID,
    financial_year: str,
    db: Session = Depends(deps.get_db),
    current_user: Union[Organization, Employee] = Depends(deps.get_current_user)
):
    is_self = not isinstance(current_user, Organization) and current_user.uuid == employee_uuid
    if not is_self:
        _require_permission(db, current_user, PayrollTaxPermissions.READ, "compare tax regimes")
    org_id = _get_org_id(current_user)
    
    employee = db.query(Employee).filter(
        Employee.uuid == employee_uuid,
        Employee.organization_id == org_id
    ).first()
    if not employee:
        raise HTTPException(404, "Employee not found")
        
    calc_old = _calculate_tax_for_emp(db, employee, org_id, financial_year, TaxRegime.OLD)
    calc_new = _calculate_tax_for_emp(db, employee, org_id, financial_year, TaxRegime.NEW)
    
    recommended = "new" if calc_new.net_tax_payable <= calc_old.net_tax_payable else "old"
    
    comparison_data = {
        "financial_year": financial_year,
        "old_regime_tax": calc_old.net_tax_payable,
        "new_regime_tax": calc_new.net_tax_payable,
        "recommended_regime": recommended
    }
    
    return {
        "success": True,
        "message": "Tax regimes compared successfully",
        "data": comparison_data
    }