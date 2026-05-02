import typing
import uuid
from typing import Any, List, Optional
from datetime import date, datetime
from fastapi import APIRouter, Depends, Query, HTTPException, status
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import or_, desc

from app.api import deps
from app.models.attendance import LeaveEncashment, LeaveEncashmentStatus, LeaveBalance, LeaveType
from app.models.employee import Employee, EmployeeHistory, ChangeType
from app.models.organization import Organization
from app.schemas.leave import (
    LeaveEncashmentListResponse, LeaveEncashmentCreate, LeaveEncashmentResponse,
    LeaveEncashmentApprove, LeaveEncashmentReject, LeaveEncashmentMarkPaid
)
from app.core.permissions import LeaveEncashmentPermissions

router = APIRouter()

@router.get("/", response_model=LeaveEncashmentListResponse)
def list_leave_encashments(
    db: Session = Depends(deps.get_db),
    current_org: Organization = Depends(deps.get_current_org),
    current_user: typing.Union[Organization, Employee] = Depends(deps.get_current_user),
    employee_uuid: Optional[uuid.UUID] = Query(None, description="Filter by Employee UUID"),
    status: Optional[str] = Query(None, description="Filter by status (pending, approved, etc)"),
    from_date: Optional[date] = Query(None, description="Filter from encashment date"),
    to_date: Optional[date] = Query(None, description="Filter to encashment date"),
    search: Optional[str] = Query(None, description="Search by employee name, code or encashment number"),
    sort_by: str = Query("created_at", description="Sort by field (created_at, employee)"),
    order: str = Query("desc", description="Sort order (asc, desc)"),
    page: int = Query(1, ge=1, description="Page number"),
    limit: int = Query(10, ge=1, description="Items per page")
):
    """
    List leave encashment requests with filtering.
    """
    query = db.query(LeaveEncashment).filter(
        LeaveEncashment.organization_id == current_org.id
    )

    # Join employee if needed for search or sorting
    if search or employee_uuid or sort_by == "employee":
        query = query.join(LeaveEncashment.employee)

    if search:
        search_filter = or_(
            LeaveEncashment.encashment_number.ilike(f"%{search}%"),
            Employee.first_name.ilike(f"%{search}%"),
            Employee.last_name.ilike(f"%{search}%"),
            Employee.employee_code.ilike(f"%{search}%")
        )
        query = query.filter(search_filter)

    if employee_uuid:
        query = query.filter(Employee.uuid == employee_uuid)

    if status:
        query = query.filter(LeaveEncashment.status == status)

    if from_date:
        query = query.filter(LeaveEncashment.encashment_date >= from_date)
    
    if to_date:
        query = query.filter(LeaveEncashment.encashment_date <= to_date)

    # RBAC: Employees only see their own requests unless they have permission (Code 51)
    if not deps.has_permission(db, current_user, LeaveEncashmentPermissions.READ):
        query = query.filter(LeaveEncashment.employee_id == current_user.id)

    # Sorting
    if sort_by == "employee":
        sort_attr = Employee.first_name
    else:
        # Default to created_at if field doesn't exist
        sort_attr = getattr(LeaveEncashment, sort_by, LeaveEncashment.created_at)

    if order.lower() == "asc":
        query = query.order_by(sort_attr)
    else:
        query = query.order_by(desc(sort_attr))

    # Pagination
    total_records = query.count()
    total_pages = (total_records + limit - 1) // limit
    
    # Apply limit/offset
    encashments = query.options(
        joinedload(LeaveEncashment.employee),
        joinedload(LeaveEncashment.leave_type),
        joinedload(LeaveEncashment.approved_by_user)
    ).offset((page - 1) * limit).limit(limit).all()

    return LeaveEncashmentListResponse(
        success=True,
        message="Leave encashments retrieved successfully",
        data=encashments,
        pagination={
            "total_records": total_records,
            "current_page": page,
            "total_pages": total_pages,
            "page_size": limit
        }
    )

@router.post("/", response_model=LeaveEncashmentResponse)
def create_leave_encashment(
    encashment_in: LeaveEncashmentCreate,
    db: Session = Depends(deps.get_db),
    current_org: Organization = Depends(deps.get_current_org),
    current_user: typing.Union[Organization, Employee] = Depends(deps.get_current_user)
):
    """
    Create a new leave encashment request.
    Verifies leave type encashability and available balance.
    """

    # 1. Resolve Employee
    employee = db.query(Employee).filter(
        Employee.uuid == encashment_in.employee_uuid,
        Employee.organization_id == current_org.id,
        Employee.is_deleted == False
    ).first()
    
    if not employee:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Employee not found"
        )
    
    # 2. Resolve Leave Type
    leave_type = db.query(LeaveType).filter(
        LeaveType.uuid == encashment_in.leave_type_uuid,
        LeaveType.organization_id == current_org.id,
        LeaveType.is_deleted == False
    ).first()
    
    if not leave_type:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Leave type not found"
        )
    
    if not leave_type.is_encashable:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Leave type '{leave_type.leave_name}' is not encashable"
        )
    
    # Ownership Check: Employees can only create encashments for themselves
    if isinstance(current_user, Employee) and current_user.uuid != encashment_in.employee_uuid:
        if not deps.has_permission(db, current_user, "52"):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied. You can only create encashment requests for yourself."
            )
    
    # 3. Get Employee's Latest Salary (for calculation)
    latest_history = db.query(EmployeeHistory).filter(
        EmployeeHistory.employee_id == employee.id,
        EmployeeHistory.new_salary.isnot(None)
    ).order_by(EmployeeHistory.effective_date.desc(), EmployeeHistory.created_at.desc()).first()
    
    if not latest_history:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Employee salary information not found. Cannot calculate encashment amount."
        )
    
    monthly_salary = latest_history.new_salary
    per_day_salary = monthly_salary / 30  # Assuming 30-day month for calculation
    
    current_year = datetime.utcnow().year
    
    # 4. Check Leave Balance
    balance = db.query(LeaveBalance).filter(
        LeaveBalance.employee_id == employee.id,
        LeaveBalance.leave_type_id == leave_type.id,
        LeaveBalance.balance_year == current_year
    ).first()
    
    if not balance:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No leave balance found for the current year"
        )
    
    if balance.available_balance < encashment_in.encashment_days:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Insufficient balance. Available: {balance.available_balance}, Requested: {encashment_in.encashment_days}"
        )
    
    # 5. Calculate Amount
    encashment_amount = per_day_salary * encashment_in.encashment_days
    tax_deducted = 0
    net_amount = encashment_amount - tax_deducted
    
    # 6. Generate Encashment Number
    timestamp = datetime.utcnow().strftime("%Y%m%d%H%M%S")
    encashment_number = f"ENC-{employee.employee_code}-{timestamp}"
    
    # 7. Create Record
    encashment = LeaveEncashment(
        organization_id=current_org.id,
        employee_id=employee.id,
        leave_type_id=leave_type.id,
        encashment_number=encashment_number,
        encashment_date=date.today(),
        leave_balance_id=balance.id,
        available_days=balance.available_balance,
        encashment_days=encashment_in.encashment_days,
        per_day_salary=per_day_salary,
        encashment_amount=encashment_amount,
        is_taxable=True,
        tax_deducted=tax_deducted,
        net_amount=net_amount,
        status=LeaveEncashmentStatus.PENDING,
        remarks=encashment_in.remarks
    )
    
    db.add(encashment)
    # Deduct from available balance immediately to prevent double-encashment while pending
    balance.available_balance -= encashment_in.encashment_days
    balance.encashed += encashment_in.encashment_days
    
    try:
        db.commit()
        db.refresh(encashment)
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create encashment request: {str(e)}"
        )
    
    # Load relationships for response
    encashment = db.query(LeaveEncashment).filter(LeaveEncashment.id == encashment.id).options(
        joinedload(LeaveEncashment.employee),
        joinedload(LeaveEncashment.leave_type)
    ).first()
    
    return LeaveEncashmentResponse(
        success=True,
        message="Leave encashment request created successfully",
        data=encashment
    )

@router.get("/{encashment_id}", response_model=LeaveEncashmentResponse)
def get_leave_encashment(
    encashment_id: str,
    db: Session = Depends(deps.get_db),
    current_org: Organization = Depends(deps.get_current_org),
    current_user: typing.Union[Organization, Employee] = Depends(deps.get_current_user)
):
    """
    Get detailed information about a specific leave encashment request.
    Supports both internal ID and UUID.
    """
    encashment = None
    try:
        # Try resolving by UUID first
        uuid_obj = uuid.UUID(encashment_id)
        encashment = db.query(LeaveEncashment).filter(
            LeaveEncashment.uuid == uuid_obj,
            LeaveEncashment.organization_id == current_org.id
        ).first()
    except ValueError:
        # Fallback to internal ID
        try:
            encashment = db.query(LeaveEncashment).filter(
                LeaveEncashment.id == int(encashment_id),
                LeaveEncashment.organization_id == current_org.id
            ).first()
        except ValueError:
            pass

    if not encashment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Leave encashment request not found"
        )

    # Ownership Check: Only allow owner or anyone with permission (Code 51)
    if not deps.has_permission(db, current_user, "51") and (isinstance(current_user, Employee) and encashment.employee_id != current_user.id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied. You can only view your own encashment requests."
        )

    # Load relationships
    encashment = db.query(LeaveEncashment).filter(LeaveEncashment.id == encashment.id).options(
        joinedload(LeaveEncashment.employee),
        joinedload(LeaveEncashment.leave_type),
        joinedload(LeaveEncashment.approved_by_user)
    ).first()

    return LeaveEncashmentResponse(
        success=True,
        message="Leave encashment details retrieved successfully",
        data=encashment
    )

@router.patch("/{encashment_id}/approve", response_model=LeaveEncashmentResponse, dependencies=[Depends(deps.check_permission("53"))])
def approve_leave_encashment(
    encashment_id: str,
    approval_in: LeaveEncashmentApprove,
    db: Session = Depends(deps.get_db),
    current_org: Organization = Depends(deps.get_current_org)
):
    """
    Approve a leave encashment request.
    """
    encashment = _get_encashment_or_404(db, encashment_id, current_org.id)

    if encashment.status != LeaveEncashmentStatus.PENDING:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Only pending requests can be approved. Current status: {encashment.status}"
        )

    encashment.status = LeaveEncashmentStatus.APPROVED
    encashment.approved_at = datetime.utcnow()
    # In a full system, you'd get the current user's employee_id from auth
    # encashment.approved_by = current_user_employee_id 
    
    if approval_in.approved_amount:
        encashment.encashment_amount = approval_in.approved_amount
        encashment.net_amount = approval_in.approved_amount - encashment.tax_deducted

    if approval_in.comments:
        encashment.remarks = f"{encashment.remarks or ''}\nApproval Comments: {approval_in.comments}".strip()

    db.commit()
    db.refresh(encashment)

    return LeaveEncashmentResponse(
        success=True,
        message="Leave encashment request approved successfully",
        data=encashment
    )

@router.patch("/{encashment_id}/reject", response_model=LeaveEncashmentResponse, dependencies=[Depends(deps.check_permission("53"))])
def reject_leave_encashment(
    encashment_id: str,
    reject_in: LeaveEncashmentReject,
    db: Session = Depends(deps.get_db),
    current_org: Organization = Depends(deps.get_current_org)
):
    """
    Reject a leave encashment request and restore the leave balance.
    """
    encashment = _get_encashment_or_404(db, encashment_id, current_org.id)

    if encashment.status != LeaveEncashmentStatus.PENDING:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Only pending requests can be rejected. Current status: {encashment.status}"
        )

    # 1. Update Status
    encashment.status = LeaveEncashmentStatus.REJECTED
    encashment.rejection_reason = reject_in.rejection_reason

    # 2. Restore Leave Balance
    balance = db.query(LeaveBalance).filter(LeaveBalance.id == encashment.leave_balance_id).first()
    if balance:
        balance.available_balance += encashment.encashment_days
        balance.encashed -= encashment.encashment_days

    db.commit()
    db.refresh(encashment)

    return LeaveEncashmentResponse(
        success=True,
        message="Leave encashment request rejected successfully",
        data=encashment
    )

@router.patch("/{encashment_id}/mark-paid", response_model=LeaveEncashmentResponse, dependencies=[Depends(deps.check_permission("53"))])
def mark_leave_encashment_paid(
    encashment_id: str,
    paid_in: LeaveEncashmentMarkPaid,
    db: Session = Depends(deps.get_db),
    current_org: Organization = Depends(deps.get_current_org)
):
    """
    Mark an approved leave encashment request as paid.
    """
    encashment = _get_encashment_or_404(db, encashment_id, current_org.id)

    if encashment.status != LeaveEncashmentStatus.APPROVED:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Only approved requests can be marked as paid. Current status: {encashment.status}"
        )

    encashment.status = LeaveEncashmentStatus.PAID
    encashment.is_paid = True
    encashment.payment_date = paid_in.payment_date
    encashment.payment_reference = paid_in.payment_reference

    db.commit()
    db.refresh(encashment)

    return LeaveEncashmentResponse(
        success=True,
        message="Leave encashment marked as paid successfully",
        data=encashment
    )

def _get_encashment_or_404(db: Session, encashment_id: str, org_id: int) -> LeaveEncashment:
    encashment = None
    try:
        uuid_obj = uuid.UUID(encashment_id)
        encashment = db.query(LeaveEncashment).filter(
            LeaveEncashment.uuid == uuid_obj,
            LeaveEncashment.organization_id == org_id
        ).first()
    except ValueError:
        try:
            encashment = db.query(LeaveEncashment).filter(
                LeaveEncashment.id == int(encashment_id),
                LeaveEncashment.organization_id == org_id
            ).first()
        except ValueError:
            pass
    
    if not encashment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Leave encashment request not found"
        )
    return encashment

@router.delete("/{encashment_id}", response_model=LeaveEncashmentResponse, dependencies=[Depends(deps.check_permission("54"))])
def delete_leave_encashment(
    encashment_id: str,
    db: Session = Depends(deps.get_db),
    current_org: Organization = Depends(deps.get_current_org)
):
    """
    Delete a leave encashment request.
    If the request is pending, it restores the leave balance.
    """
    encashment = _get_encashment_or_404(db, encashment_id, current_org.id)

    # 1. If pending, restore balance
    if encashment.status == LeaveEncashmentStatus.PENDING:
        balance = db.query(LeaveBalance).filter(LeaveBalance.id == encashment.leave_balance_id).first()
        if balance:
            balance.available_balance += encashment.encashment_days
            balance.encashed -= encashment.encashment_days

    # 2. Delete record
    db.delete(encashment)
    
    try:
        db.commit()
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete encashment request: {str(e)}"
        )

    return LeaveEncashmentResponse(
        success=True,
        message="Leave encashment request deleted successfully",
        data=None
    )
