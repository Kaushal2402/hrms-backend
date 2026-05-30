import uuid
from typing import List, Optional, Union
from datetime import date, datetime, timedelta
from decimal import Decimal
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from sqlalchemy import func, or_

from app.api import deps
from app.models.organization import Organization
from app.models.employee import Employee
from app.models.payroll import EmployeeLoan, LoanRepayment, LoanStatus
from app.schemas.payroll_loans import (
    LoanCreate, LoanUpdate, LoanReject, LoanSchema, LoanResponse, 
    LoanListResponse, LoanRepaymentListResponse, LoanDisbursementUpdate,
    EmployeeLoanListResponse
)

router = APIRouter()

class PayrollLoanPermissions:
    READ = "116"
    CREATE = "117"
    APPROVE = "118"
    UPDATE = "117"

def _get_org_id(current_user: Union[Organization, Employee]) -> int:
    return current_user.id if isinstance(current_user, Organization) else current_user.organization_id

def _require_permission(db, current_user, code, action_label):
    if isinstance(current_user, Organization): return
    if not deps.has_permission(db, current_user, code):
        raise HTTPException(status_code=403, detail=f"Permission denied: {action_label}")

@router.get("/", response_model=LoanListResponse)
def get_loans(
    page: int = Query(1, ge=1),
    limit: int = Query(10, ge=1, le=100),
    search: Optional[str] = None,
    status: Optional[LoanStatus] = None,
    loan_type: Optional[str] = None,
    sort_by: str = Query("created_at"),
    sort_order: str = Query("desc"),
    db: Session = Depends(deps.get_db),
    current_user: Union[Organization, Employee] = Depends(deps.get_current_user)
):
    _require_permission(db, current_user, PayrollLoanPermissions.READ, "list")
    org_id = _get_org_id(current_user)
    
    query = db.query(EmployeeLoan).filter(EmployeeLoan.organization_id == org_id)
    if status: query = query.filter(EmployeeLoan.status == status)
    if loan_type: query = query.filter(EmployeeLoan.loan_type == loan_type)
    
    if search:
        query = query.join(Employee, EmployeeLoan.employee_id == Employee.id).filter(
            or_(
                EmployeeLoan.loan_number.ilike(f"%{search}%"),
                Employee.first_name.ilike(f"%{search}%"),
                Employee.last_name.ilike(f"%{search}%")
            )
        )
    
    allowed_sort = ["created_at", "loan_amount", "loan_number", "status"]
    sort_field = sort_by if sort_by in allowed_sort else "created_at"
    
    if sort_order.lower() == "asc":
        query = query.order_by(getattr(EmployeeLoan, sort_field).asc())
    else:
        query = query.order_by(getattr(EmployeeLoan, sort_field).desc())
    
    total = query.count()
    items = query.offset((page - 1) * limit).limit(limit).all()
    return LoanListResponse(success=True, message="Loans retrieved", data=items, 
                            pagination={"total_records": total, "current_page": page, "total_pages": (total + limit - 1) // limit, "page_size": limit})

@router.post("/", response_model=LoanResponse)
def create_loan(
    item_in: LoanCreate,
    db: Session = Depends(deps.get_db),
    current_user: Union[Organization, Employee] = Depends(deps.get_current_user)
):
    _require_permission(db, current_user, PayrollLoanPermissions.CREATE, "create")
    org_id = _get_org_id(current_user)
    emp = db.query(Employee).filter(Employee.uuid == item_in.employee_uuid, Employee.organization_id == org_id).first()
    if not emp: raise HTTPException(404, "Employee not found")
    
    loan_num = f"LN-{emp.employee_code}-{datetime.now().strftime('%Y%m%d%H%M%S')}"
    loan = EmployeeLoan(organization_id=org_id, employee_id=emp.id, loan_number=loan_num, **item_in.model_dump(exclude={'employee_uuid'}), outstanding_amount=item_in.total_payable)
    db.add(loan); db.commit(); db.refresh(loan)
    return LoanResponse(success=True, message="Loan created", data=loan)

@router.get("/pending-repayments", response_model=LoanRepaymentListResponse)
def get_pending(loan_uuid: Optional[uuid.UUID] = None, db: Session = Depends(deps.get_db), current_user: Union[Organization, Employee] = Depends(deps.get_current_user)):
    query = db.query(LoanRepayment).join(EmployeeLoan).filter(EmployeeLoan.organization_id == _get_org_id(current_user), LoanRepayment.is_paid == False, LoanRepayment.due_date <= date.today())
    if loan_uuid:
        query = query.filter(EmployeeLoan.uuid == loan_uuid)
    pending = query.all()
    return LoanRepaymentListResponse(success=True, message="Pending repayments", data=pending)

@router.get("/{loan_uuid}", response_model=LoanResponse)
def get_loan(loan_uuid: uuid.UUID, db: Session = Depends(deps.get_db), current_user: Union[Organization, Employee] = Depends(deps.get_current_user)):
    loan = db.query(EmployeeLoan).filter(EmployeeLoan.uuid == loan_uuid, EmployeeLoan.organization_id == _get_org_id(current_user)).first()
    if not loan: raise HTTPException(404, "Loan not found")
    return LoanResponse(success=True, message="Loan retrieved", data=loan)

@router.put("/{loan_uuid}", response_model=LoanResponse)
def update_loan(
    loan_uuid: uuid.UUID,
    item_in: LoanUpdate,
    db: Session = Depends(deps.get_db),
    current_user: Union[Organization, Employee] = Depends(deps.get_current_user)
):
    _require_permission(db, current_user, PayrollLoanPermissions.UPDATE, "update")
    loan = db.query(EmployeeLoan).filter(EmployeeLoan.uuid == loan_uuid, EmployeeLoan.organization_id == _get_org_id(current_user)).first()
    if not loan: raise HTTPException(404, "Loan not found")
    if loan.status != LoanStatus.PENDING: raise HTTPException(400, "Cannot update non-pending loan")
    
    update_data = item_in.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(loan, field, value)
    
    # Recalculate outstanding amount after updating total_payable
    loan.outstanding_amount = loan.total_payable - (loan.amount_paid or 0)
    
    db.commit()
    db.refresh(loan)
    return LoanResponse(success=True, message="Loan updated successfully", data=loan)

@router.post("/{loan_uuid}/approve", response_model=LoanResponse)
def approve_loan(loan_uuid: uuid.UUID, db: Session = Depends(deps.get_db), current_user: Union[Organization, Employee] = Depends(deps.get_current_user)):
    _require_permission(db, current_user, PayrollLoanPermissions.APPROVE, "approve")
    loan = db.query(EmployeeLoan).filter(EmployeeLoan.uuid == loan_uuid, EmployeeLoan.organization_id == _get_org_id(current_user)).first()
    if not loan or loan.status != LoanStatus.PENDING: raise HTTPException(400, "Invalid status for approval")
    loan.status = LoanStatus.APPROVED
    db.commit(); db.refresh(loan)
    return LoanResponse(success=True, message="Loan approved", data=loan)

@router.post("/{loan_uuid}/reject", response_model=LoanResponse)
def reject_loan(
    loan_uuid: uuid.UUID,
    item_in: LoanReject,
    db: Session = Depends(deps.get_db),
    current_user: Union[Organization, Employee] = Depends(deps.get_current_user)
):
    _require_permission(db, current_user, PayrollLoanPermissions.APPROVE, "reject")
    loan = db.query(EmployeeLoan).filter(EmployeeLoan.uuid == loan_uuid, EmployeeLoan.organization_id == _get_org_id(current_user)).first()
    if not loan or loan.status != LoanStatus.PENDING: raise HTTPException(400, "Invalid status for rejection")
    
    loan.status = LoanStatus.REJECTED
    loan.notes = f"Rejected: {item_in.rejection_reason}"
    db.commit()
    db.refresh(loan)
    return LoanResponse(success=True, message="Loan rejected", data=loan)

@router.post("/{loan_uuid}/disburse", response_model=LoanResponse)
def disburse_loan(loan_uuid: uuid.UUID, data: LoanDisbursementUpdate, db: Session = Depends(deps.get_db), current_user: Union[Organization, Employee] = Depends(deps.get_current_user)):
    loan = db.query(EmployeeLoan).filter(EmployeeLoan.uuid == loan_uuid, EmployeeLoan.organization_id == _get_org_id(current_user)).first()
    if not loan or loan.status != LoanStatus.APPROVED: raise HTTPException(400, "Loan not approved")
    
    loan.status = LoanStatus.ACTIVE
    loan.disbursement_date = data.disbursement_date
    loan.disbursement_mode = data.disbursement_mode
    loan.disbursement_reference = data.disbursement_reference
    
    # Generate Schedule
    monthly_total = loan.total_payable / loan.number_of_installments
    interest_per_month = (loan.loan_amount * (loan.interest_rate / 100)) / loan.number_of_installments
    principal_per_month = monthly_total - interest_per_month
    
    for i in range(1, loan.number_of_installments + 1):
        due_date = loan.repayment_start_date + timedelta(days=30 * (i - 1))
        db.add(LoanRepayment(loan_id=loan.id, installment_number=i, due_date=due_date, principal_amount=principal_per_month, interest_amount=interest_per_month, total_amount=monthly_total))
    
    db.commit(); db.refresh(loan)
    return LoanResponse(success=True, message="Loan disbursed", data=loan)

@router.get("/{loan_uuid}/repayment-schedule", response_model=LoanRepaymentListResponse)
def get_schedule(loan_uuid: uuid.UUID, db: Session = Depends(deps.get_db), current_user: Union[Organization, Employee] = Depends(deps.get_current_user)):
    loan = db.query(EmployeeLoan).filter(EmployeeLoan.uuid == loan_uuid, EmployeeLoan.organization_id == _get_org_id(current_user)).first()
    if not loan: raise HTTPException(404, "Loan not found")
    schedules = db.query(LoanRepayment).filter(LoanRepayment.loan_id == loan.id).order_by(LoanRepayment.due_date).all()
    return LoanRepaymentListResponse(success=True, message="Schedule retrieved", data=schedules)


@router.get("/employees/{employee_uuid}/loans", response_model=EmployeeLoanListResponse)
def get_employee_loans(
    employee_uuid: uuid.UUID,
    search: Optional[str] = None,
    status: Optional[LoanStatus] = None,
    include_completed: bool = False,
    page: int = Query(1, ge=1),
    limit: int = Query(10, ge=1, le=100),
    sort_by: str = Query("created_at"),
    order: str = Query("desc"),
    db: Session = Depends(deps.get_db),
    current_user: Union[Organization, Employee] = Depends(deps.get_current_user)
):
    org_id = _get_org_id(current_user)
    emp = db.query(Employee).filter(Employee.uuid == employee_uuid, Employee.organization_id == org_id).first()
    if not emp: raise HTTPException(404, "Employee not found")
    
    # Base query for summaries
    summary_query = db.query(
        func.coalesce(func.sum(EmployeeLoan.loan_amount), 0),
        func.coalesce(func.sum(EmployeeLoan.outstanding_amount), 0),
        func.coalesce(func.sum(EmployeeLoan.amount_paid), 0)
    ).filter(EmployeeLoan.employee_id == emp.id, EmployeeLoan.organization_id == org_id)
    total_sanc, out_bal, tot_paid = summary_query.first()
    
    emi_query = db.query(
        func.coalesce(func.sum(EmployeeLoan.monthly_installment), 0)
    ).filter(EmployeeLoan.employee_id == emp.id, EmployeeLoan.organization_id == org_id, EmployeeLoan.status == LoanStatus.ACTIVE)
    monthly_emi = emi_query.scalar()
    
    # Query for items
    query = db.query(EmployeeLoan).filter(EmployeeLoan.employee_id == emp.id, EmployeeLoan.organization_id == org_id)
    if status:
        query = query.filter(EmployeeLoan.status == status)
    elif not include_completed:
        query = query.filter(EmployeeLoan.status != LoanStatus.COMPLETED)
        
    if search:
        query = query.filter(
            or_(
                EmployeeLoan.loan_number.ilike(f"%{search}%"),
                EmployeeLoan.purpose.ilike(f"%{search}%")
            )
        )
        
    total = query.count()
    
    # Safe sorting
    sort_col = getattr(EmployeeLoan, sort_by, EmployeeLoan.created_at)
    if order.lower() == "asc":
        query = query.order_by(sort_col.asc())
    else:
        query = query.order_by(sort_col.desc())
        
    items = query.offset((page - 1) * limit).limit(limit).all()
    
    return EmployeeLoanListResponse(
        success=True, 
        message="Employee loans retrieved successfully", 
        data=items,
        pagination={"total_records": total, "current_page": page, "total_pages": (total + limit - 1) // limit, "page_size": limit},
        summary={
            "total_sanctioned": total_sanc,
            "outstanding_balance": out_bal,
            "total_repaid": tot_paid,
            "monthly_emi_commitment": monthly_emi
        }
    )