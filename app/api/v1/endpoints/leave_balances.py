import uuid
from datetime import datetime, date
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session, joinedload
from fastapi.responses import JSONResponse

from app.api import deps
from app.models.attendance import LeaveBalance, LeaveType, LeaveAccrualHistory, LeavePolicy, LeavePolicyMapping, LeaveAccrualType
from app.models.employee import Employee, Department
from app.models.organization import Organization
from app.schemas.leave import (
    LeaveCreditCreate, LeaveBalanceResponse, LeaveDebitCreate, 
    AccrualProcessRequest, AccrualProcessResponse, AccrualSummary,
    CarryForwardRequest, CarryForwardResponse, CarryForwardSummary,
    LeaveBalanceListResponse, EmployeeLeaveListResponse
)

router = APIRouter()

@router.post("/credit", response_model=LeaveBalanceResponse)
def credit_leave_balance(
    credit_in: LeaveCreditCreate,
    db: Session = Depends(deps.get_db),
    current_org: Organization = Depends(deps.get_current_org),
    authorized: bool = Depends(deps.check_permission("53"))
):
    """
    Manually credit leave days to an employee's leave balance.
    """
    # 1. Resolve Employee
    employee = db.query(Employee).filter(
        Employee.uuid == credit_in.employee_uuid,
        Employee.organization_id == current_org.id
    ).first()
    
    if not employee:
        return JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND,
            content={"success": False, "message": "Employee not found", "data": None}
        )
        
    # 2. Resolve Leave Type
    leave_type = db.query(LeaveType).filter(
        LeaveType.uuid == credit_in.leave_type_uuid,
        LeaveType.organization_id == current_org.id,
        LeaveType.is_deleted == False
    ).first()
    
    if not leave_type:
        return JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND,
            content={"success": False, "message": "Leave type not found", "data": None}
        )
        
    # 3. Determine Balance Year
    balance_year = credit_in.year or datetime.utcnow().year
    
    # 4. Get or Create Leave Balance record
    balance = db.query(LeaveBalance).filter(
        LeaveBalance.employee_id == employee.id,
        LeaveBalance.leave_type_id == leave_type.id,
        LeaveBalance.balance_year == balance_year
    ).first()
    
    if not balance:
        # Create a new balance record if it doesn't exist for the year
        # Note: In a full system, you'd calculate period start/end based on fiscal year settings
        period_start = date(balance_year, 1, 1)
        period_end = date(balance_year, 12, 31)
        
        balance = LeaveBalance(
            organization_id=current_org.id,
            employee_id=employee.id,
            leave_type_id=leave_type.id,
            balance_year=balance_year,
            period_start_date=period_start,
            period_end_date=period_end,
            opening_balance=0,
            brought_forward=0,
            accrued=0,
            credited=0,
            used=0,
            pending_approval=0,
            adjusted=0,
            encashed=0,
            lapsed=0,
            available_balance=0,
            total_balance=0
        )
        db.add(balance)
        db.flush()
        
    # 5. Update Balance
    balance.credited += credit_in.days
    balance.available_balance += credit_in.days
    balance.total_balance += credit_in.days
    
    # 6. Record in History
    history = LeaveAccrualHistory(
        employee_id=employee.id,
        leave_type_id=leave_type.id,
        leave_balance_id=balance.id,
        accrual_date=date.today(),
        accrual_period=f"Manual-{datetime.utcnow().strftime('%b-%Y')}",
        accrued_days=credit_in.days,
        transaction_type="manual_credit",
        remarks=credit_in.reason,
        balance_after=balance.available_balance
    )
    db.add(history)
    
    db.commit()
    db.refresh(balance)
    
    # Reload with relationships
    balance = db.query(LeaveBalance).filter(LeaveBalance.id == balance.id).options(
        joinedload(LeaveBalance.leave_type)
    ).first()
    
    return LeaveBalanceResponse(
        success=True,
        message=f"Successfully credited {credit_in.days} days to {leave_type.leave_name}",
        data=balance
    )

@router.get("/", response_model=LeaveBalanceListResponse)
def list_leave_balances(
    db: Session = Depends(deps.get_db),
    current_org: Organization = Depends(deps.get_current_org),
    authorized: bool = Depends(deps.check_permission("51"))
):
    """
    List all leave balances for the organization.
    """
    balances = db.query(LeaveBalance).filter(
        LeaveBalance.organization_id == current_org.id
    ).options(
        joinedload(LeaveBalance.leave_type)
    ).all()
    
    return LeaveBalanceListResponse(
        success=True,
        message="Leave balances retrieved successfully",
        data=balances
    )

@router.get("/employee-leaves", response_model=EmployeeLeaveListResponse)
def get_employee_leaves(
    db: Session = Depends(deps.get_db),
    current_org: Organization = Depends(deps.get_current_org),
    authorized: bool = Depends(deps.check_permission("51")),
    page: Optional[int] = Query(None, ge=1, description="Page number"),
    limit: int = Query(10, ge=1, description="Items per page"),
    search: Optional[str] = Query(None, description="Search by employee name or code"),
    sort_by: str = Query("employee", description="Sort by employee name"),
    order: str = Query("asc", description="Sort order (asc, desc)"),
    department_uuid: Optional[uuid.UUID] = Query(None, description="Filter by department UUID")
):
    """
    Get all employees with specific statuses and their leave balances.
    Statuses: ACTIVE, ON_LEAVE, PROBATION, NOTICE_PERIOD, RESIGNED.
    With Pagination, Search, and Sort.
    """
    from app.models.employee import EmploymentStatus
    
    target_statuses = [
        EmploymentStatus.ACTIVE,
        EmploymentStatus.ON_LEAVE,
        EmploymentStatus.PROBATION,
        EmploymentStatus.NOTICE_PERIOD,
        EmploymentStatus.RESIGNED
    ]
    
    # 1. Base Query
    query = db.query(Employee).filter(
        Employee.organization_id == current_org.id,
        Employee.employment_status.in_(target_statuses),
        Employee.is_deleted == False
    )
    
    # 2. Department filtering
    if department_uuid:
        query = query.join(Department, Employee.department_id == Department.id).filter(
            Department.uuid == department_uuid
        )
        
    # 3. Search filtering
    if search:
        search_term = f"%{search}%"
        query = query.filter(
            (Employee.first_name.ilike(search_term)) |
            (Employee.last_name.ilike(search_term)) |
            (Employee.employee_code.ilike(search_term))
        )
        
    # 4. Sorting
    if sort_by == "employee":
        if order.lower() == "desc":
            query = query.order_by(Employee.first_name.desc(), Employee.last_name.desc())
        else:
            query = query.order_by(Employee.first_name.asc(), Employee.last_name.asc())
    else:
        # Default sort
        query = query.order_by(Employee.first_name.asc())
        
    # 5. Pagination
    total_records = query.count()
    
    pagination_data = None
    if page is not None:
        total_pages = (total_records + limit - 1) // limit
        skip = (page - 1) * limit
        employees = query.offset(skip).limit(limit).all()
        pagination_data = {
            "total_records": total_records,
            "current_page": page,
            "total_pages": total_pages,
            "page_size": limit
        }
    else:
        employees = query.all()
        pagination_data = {
            "total_records": total_records,
            "current_page": 1,
            "total_pages": 1,
            "page_size": total_records if total_records > 0 else 0
        }
        
    # 6. Load Relationships and Balances
    current_year = date.today().year
    result = []
    
    for emp in employees:
        balances = db.query(LeaveBalance).filter(
            LeaveBalance.employee_id == emp.id,
            LeaveBalance.balance_year == current_year
        ).options(
            joinedload(LeaveBalance.leave_type)
        ).all()
        
        result.append({
            "employee": emp,
            "leave_balances": balances
        })
        
    return EmployeeLeaveListResponse(
        success=True,
        message="Employee leave balances retrieved successfully",
        data=result,
        pagination=pagination_data
    )

@router.get("/{balance_uuid}", response_model=LeaveBalanceResponse)
def get_leave_balance(
    balance_uuid: uuid.UUID,
    db: Session = Depends(deps.get_db),
    current_org: Organization = Depends(deps.get_current_org),
    authorized: bool = Depends(deps.check_permission("51"))
):
    """
    Get specific leave balance details.
    """
    balance = db.query(LeaveBalance).filter(
        LeaveBalance.uuid == balance_uuid,
        LeaveBalance.organization_id == current_org.id
    ).options(
        joinedload(LeaveBalance.leave_type)
    ).first()
    
    if not balance:
        return JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND,
            content={"success": False, "message": "Leave balance not found", "data": None}
        )
        
    return LeaveBalanceResponse(
        success=True,
        message="Leave balance retrieved successfully",
        data=balance
    )

@router.post("/debit", response_model=LeaveBalanceResponse)
def debit_leave_balance(
    debit_in: LeaveDebitCreate,
    db: Session = Depends(deps.get_db),
    current_org: Organization = Depends(deps.get_current_org),
    authorized: bool = Depends(deps.check_permission("53"))
):
    """
    Manually debit (deduct) leave days from an employee's leave balance.
    """
    # 1. Resolve Employee
    employee = db.query(Employee).filter(
        Employee.uuid == debit_in.employee_uuid,
        Employee.organization_id == current_org.id
    ).first()
    
    if not employee:
        return JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND,
            content={"success": False, "message": "Employee not found", "data": None}
        )
        
    # 2. Resolve Leave Type
    leave_type = db.query(LeaveType).filter(
        LeaveType.uuid == debit_in.leave_type_uuid,
        LeaveType.organization_id == current_org.id,
        LeaveType.is_deleted == False
    ).first()
    
    if not leave_type:
        return JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND,
            content={"success": False, "message": "Leave type not found", "data": None}
        )
        
    # 3. Determine Balance Year
    balance_year = debit_in.year or datetime.utcnow().year
    
    # 4. Get Leave Balance record
    balance = db.query(LeaveBalance).filter(
        LeaveBalance.employee_id == employee.id,
        LeaveBalance.leave_type_id == leave_type.id,
        LeaveBalance.balance_year == balance_year
    ).first()
    
    if not balance:
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={"success": False, "message": f"No leave balance found for year {balance_year} to debit from.", "data": None}
        )
        
    # 5. Check if deduction is possible (unless leave type allows negative balance)
    if not leave_type.allow_negative_balance and (balance.available_balance - debit_in.days < 0):
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={
                "success": False, 
                "message": f"Insufficient balance. Current balance is {balance.available_balance}, cannot debit {debit_in.days}.", 
                "data": None
            }
        )
    
    # Check max negative balance if allowed
    if leave_type.allow_negative_balance and leave_type.max_negative_balance is not None:
        if (balance.available_balance - debit_in.days) < -leave_type.max_negative_balance:
            return JSONResponse(
                status_code=status.HTTP_400_BAD_REQUEST,
                content={
                    "success": False, 
                    "message": f"Debit exceeds maximum negative balance limit of {leave_type.max_negative_balance}.", 
                    "data": None
                }
            )

    # 6. Update Balance
    balance.adjusted += debit_in.days # Recording deduction as adjustment
    balance.available_balance -= debit_in.days
    balance.total_balance -= debit_in.days
    
    # 7. Record in History
    history = LeaveAccrualHistory(
        employee_id=employee.id,
        leave_type_id=leave_type.id,
        leave_balance_id=balance.id,
        accrual_date=date.today(),
        accrual_period=f"Manual-Debit-{datetime.utcnow().strftime('%b-%Y')}",
        accrued_days=-debit_in.days, # Negative for history tracking
        transaction_type="manual_debit",
        remarks=debit_in.reason,
        balance_after=balance.available_balance
    )
    db.add(history)
    
    db.commit()
    db.refresh(balance)
    
    # Reload with relationships
    balance = db.query(LeaveBalance).filter(LeaveBalance.id == balance.id).options(
        joinedload(LeaveBalance.leave_type)
    ).first()
    
    return LeaveBalanceResponse(
        success=True,
        message=f"Successfully debited {debit_in.days} days from {leave_type.leave_name}",
        data=balance
    )

@router.post("/process-accruals", response_model=AccrualProcessResponse)
def process_accruals(
    request: AccrualProcessRequest,
    db: Session = Depends(deps.get_db),
    current_org: Organization = Depends(deps.get_current_org),
    authorized: bool = Depends(deps.check_permission("53"))
):
    """
    Process leave accruals for employees based on their assigned/applicable policies.
    """
    summary = AccrualSummary(total_employees_processed=0, total_accruals_created=0)
    
    # 1. Fetch Employees
    emp_query = db.query(Employee).filter(
        Employee.organization_id == current_org.id,
        Employee.is_active == True,
        Employee.is_deleted == False
    )
    
    if request.employee_uuids:
        emp_query = emp_query.filter(Employee.uuid.in_(request.employee_uuids))
        
    employees = emp_query.all()
    
    # 2. Process each employee
    for employee in employees:
        summary.total_employees_processed += 1
        
        # 3. Find applicable policy
        # Preference: 1. Specific Match, 2. Default Policy
        # For simplicity, we'll look for a policy where applicable_to is 'all' or specific matches
        policy = db.query(LeavePolicy).filter(
            LeavePolicy.organization_id == current_org.id,
            LeavePolicy.is_active == True,
            LeavePolicy.is_deleted == False,
            (
                (LeavePolicy.applicable_to == 'all') | 
                (LeavePolicy.is_default == True)
            )
        ).order_by(LeavePolicy.is_default.asc()).first() # Policy 'all' takes precedence over 'default' if both exist
        
        if not policy:
            summary.errors.append(f"No active leave policy found for employee {employee.employee_code}")
            continue
            
        # 4. Process each leave type in the policy
        mappings = db.query(LeavePolicyMapping).filter(
            LeavePolicyMapping.leave_policy_id == policy.id,
            LeavePolicyMapping.is_active == True
        ).options(joinedload(LeavePolicyMapping.leave_type)).all()
        
        for mapping in mappings:
            leave_type = mapping.leave_type
            if not leave_type or leave_type.is_deleted:
                continue
                
            # 5. Check if accrual is due
            # Logic: We check if an accrual has already been done for this period
            accrual_due = False
            accrual_period = ""
            
            if leave_type.accrual_type == LeaveAccrualType.MONTHLY:
                accrual_period = request.accrual_date.strftime("%b-%Y")
                accrual_due = True # Monthly accruals happen every month
            elif leave_type.accrual_type == LeaveAccrualType.YEARLY:
                accrual_period = request.accrual_date.strftime("%Y")
                # For yearly, we typically only accrue once a year (e.g. in Jan)
                if request.accrual_date.month == 1:
                    accrual_due = True
                    
            if not accrual_due:
                continue
                
            # Check if history already exists for this period/type/employee
            existing_history = db.query(LeaveAccrualHistory).filter(
                LeaveAccrualHistory.employee_id == employee.id,
                LeaveAccrualHistory.leave_type_id == leave_type.id,
                LeaveAccrualHistory.accrual_period == accrual_period,
                LeaveAccrualHistory.transaction_type == ('monthly_accrual' if leave_type.accrual_type == LeaveAccrualType.MONTHLY else 'yearly_credit')
            ).first()
            
            if existing_history:
                continue # Already processed for this period
                
            # 6. Calculate Accrual Rate
            # Use policy mapping override if available, else master rate
            accrual_rate = mapping.accrual_rate_override if mapping.accrual_rate_override is not None else leave_type.accrual_rate
            
            if accrual_rate <= 0:
                continue
                
            # 7. Update/Create Balance
            balance_year = request.accrual_date.year
            balance = db.query(LeaveBalance).filter(
                LeaveBalance.employee_id == employee.id,
                LeaveBalance.leave_type_id == leave_type.id,
                LeaveBalance.balance_year == balance_year
            ).first()
            
            if not balance:
                # Create default balance if missing
                period_start = date(balance_year, 1, 1)
                period_end = date(balance_year, 12, 31)
                balance = LeaveBalance(
                    organization_id=current_org.id,
                    employee_id=employee.id,
                    leave_type_id=leave_type.id,
                    balance_year=balance_year,
                    period_start_date=period_start,
                    period_end_date=period_end,
                    available_balance=0,
                    total_balance=0
                )
                db.add(balance)
                db.flush()
                
            # 8. Record Transaction
            balance.accrued += accrual_rate
            balance.available_balance += accrual_rate
            balance.total_balance += accrual_rate
            balance.last_accrual_date = request.accrual_date
            
            history = LeaveAccrualHistory(
                employee_id=employee.id,
                leave_type_id=leave_type.id,
                leave_balance_id=balance.id,
                accrual_date=request.accrual_date,
                accrual_period=accrual_period,
                accrued_days=accrual_rate,
                transaction_type='monthly_accrual' if leave_type.accrual_type == LeaveAccrualType.MONTHLY else 'yearly_credit',
                remarks=f"Automatic {leave_type.accrual_type.value} accrual for {accrual_period}",
                balance_after=balance.available_balance
            )
            db.add(history)
            summary.total_accruals_created += 1
            
    db.commit()
    
    return AccrualProcessResponse(
        success=True,
        message=f"Process completed. {summary.total_accruals_created} accruals processed for {summary.total_employees_processed} employees.",
        data=summary
    )

@router.post("/carry-forward", response_model=CarryForwardResponse)
def process_carry_forward(
    request: CarryForwardRequest,
    db: Session = Depends(deps.get_db),
    current_org: Organization = Depends(deps.get_current_org),
    authorized: bool = Depends(deps.check_permission("53"))
):
    """
    Process year-end leave carry forward. 
    Transfers eligible unused leave balance from 'from_year' to 'to_year'.
    """
    from decimal import Decimal
    summary = CarryForwardSummary(
        total_employees_processed=0, 
        total_records_carried_forward=0,
        total_days_carried_forward=Decimal('0.00')
    )
    
    # 1. Fetch Employees
    emp_query = db.query(Employee).filter(
        Employee.organization_id == current_org.id,
        Employee.is_active == True,
        Employee.is_deleted == False
    )
    
    if request.employee_uuids:
        emp_query = emp_query.filter(Employee.uuid.in_(request.employee_uuids))
        
    employees = emp_query.all()
    
    # 2. Process each employee
    for employee in employees:
        summary.total_employees_processed += 1
        
        # 3. Get balances for the source year
        balances = db.query(LeaveBalance).filter(
            LeaveBalance.employee_id == employee.id,
            LeaveBalance.balance_year == request.from_year
        ).options(joinedload(LeaveBalance.leave_type)).all()
        
        for from_balance in balances:
            leave_type = from_balance.leave_type
            
            # 4. Check eligibility
            if not leave_type or not leave_type.is_carry_forward:
                continue
                
            available = from_balance.available_balance
            if available <= 0:
                continue
                
            # 5. Calculate carry forward amount
            carry_amount = available
            if leave_type.max_carry_forward is not None:
                carry_amount = min(available, leave_type.max_carry_forward)
                
            if carry_amount <= 0:
                continue
                
            # 6. Check if already carried forward
            existing_to_history = db.query(LeaveAccrualHistory).filter(
                LeaveAccrualHistory.employee_id == employee.id,
                LeaveAccrualHistory.leave_type_id == leave_type.id,
                LeaveAccrualHistory.accrual_period == f"CF-{request.from_year}-{request.to_year}",
                LeaveAccrualHistory.transaction_type == 'carry_forward'
            ).first()
            
            if existing_to_history:
                continue # Skip if already processed
                
            # 7. Update/Create target year balance
            to_balance = db.query(LeaveBalance).filter(
                LeaveBalance.employee_id == employee.id,
                LeaveBalance.leave_type_id == leave_type.id,
                LeaveBalance.balance_year == request.to_year
            ).first()
            
            if not to_balance:
                # Create default balance for target year if missing
                period_start = date(request.to_year, 1, 1)
                period_end = date(request.to_year, 12, 31)
                to_balance = LeaveBalance(
                    organization_id=current_org.id,
                    employee_id=employee.id,
                    leave_type_id=leave_type.id,
                    balance_year=request.to_year,
                    period_start_date=period_start,
                    period_end_date=period_end,
                    available_balance=0,
                    total_balance=0
                )
                db.add(to_balance)
                db.flush()
                
            # 8. Perform transfer
            from_balance.carry_forward_to_next_year = carry_amount
            to_balance.brought_forward += carry_amount
            to_balance.available_balance += carry_amount
            to_balance.total_balance += carry_amount
            
            # 9. Record transitions
            # History for target year
            history = LeaveAccrualHistory(
                employee_id=employee.id,
                leave_type_id=leave_type.id,
                leave_balance_id=to_balance.id,
                accrual_date=date.today(),
                accrual_period=f"CF-{request.from_year}-{request.to_year}",
                accrued_days=carry_amount,
                transaction_type='carry_forward',
                remarks=f"Leave carry forward from {request.from_year}. Remaining: {available}, Carried: {carry_amount}",
                balance_after=to_balance.available_balance
            )
            db.add(history)
            
            summary.total_records_carried_forward += 1
            summary.total_days_carried_forward += Decimal(str(carry_amount))
            
    db.commit()
    
    return CarryForwardResponse(
        success=True,
        message=f"Year-end carry forward from {request.from_year} to {request.to_year} completed successfully.",
        data=summary
    )
