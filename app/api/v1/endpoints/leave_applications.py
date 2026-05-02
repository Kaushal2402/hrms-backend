import uuid
from decimal import Decimal
from datetime import date, datetime
from typing import List, Optional, Union
from fastapi import APIRouter, Depends, HTTPException, Query, status, File, UploadFile, Form
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import or_, and_

from app.api import deps
from app.models.attendance import LeaveApplication, LeaveType, LeaveStatus, LeaveBalance, LeaveApprovalHistory, CompensatoryOff
from app.models.employee import Employee
from app.models.organization import Organization
from app.schemas.leave import (
    LeaveApplicationListResponse, LeaveApplicationCreate, LeaveApplicationResponse, 
    LeaveApplicationUpdate, LeaveActionRequest, LeaveConflictCheckRequest, LeaveConflictCheckResponse,
    BulkLeaveApprovalRequest, BulkLeaveApprovalResponse, BulkLeaveApprovalSummary,
    BulkLeaveRejectRequest
)
from fastapi.responses import JSONResponse
from sqlalchemy import func
from app.utils.upload import save_upload_file

from app.core.permissions import LeaveApplicationPermissions

router = APIRouter()

@router.get("/", response_model=LeaveApplicationListResponse, dependencies=[Depends(deps.check_permission(LeaveApplicationPermissions.READ))])
def list_leave_applications(
    db: Session = Depends(deps.get_db),
    current_org: Organization = Depends(deps.get_current_org),
    employee_uuid: Optional[uuid.UUID] = Query(None, description="Filter by employee UUID"),
    status: Optional[str] = Query(None, description="Filter by status (pending, approved, rejected, cancelled)"),
    leave_type_uuid: Optional[uuid.UUID] = Query(None, description="Filter by leave type UUID"),
    from_date: Optional[date] = Query(None, description="Filter by from date"),
    to_date: Optional[date] = Query(None, description="Filter by to date"),
    approver_uuid: Optional[uuid.UUID] = Query(None, description="Filter by current approver UUID"),
    search: Optional[str] = Query(None, description="Search by employee name or code"),
    sort_by: Optional[str] = Query(None, description="Sort by: employee (optional)"),
    order: Optional[str] = Query("desc", regex="^(asc|desc)$", description="Sort order: asc or desc"),
    page: int = Query(1, ge=1, description="Page number"),
    limit: int = Query(10, ge=1, description="Items per page")
):
    """
    List leave applications with filtering and pagination.
    """
    query = db.query(LeaveApplication).filter(
        LeaveApplication.organization_id == current_org.id
    )

    # Filters
    if employee_uuid:
        employee = db.query(Employee).filter(Employee.uuid == employee_uuid).first()
        if employee:
            query = query.filter(LeaveApplication.employee_id == employee.id)
        else:
            return LeaveApplicationListResponse(
                success=True,
                message="Employee not found",
                data=[],
                pagination={"total_records": 0, "current_page": page, "total_pages": 0, "page_size": limit}
            )

    if status:
        query = query.filter(LeaveApplication.status == status)

    if leave_type_uuid:
        leave_type = db.query(LeaveType).filter(LeaveType.uuid == leave_type_uuid).first()
        if leave_type:
            query = query.filter(LeaveApplication.leave_type_id == leave_type.id)
        else:
             return LeaveApplicationListResponse(
                success=True,
                message="Leave type not found",
                data=[],
                pagination={"total_records": 0, "current_page": page, "total_pages": 0, "page_size": limit}
            )

    if from_date:
        query = query.filter(LeaveApplication.from_date >= from_date)
    if to_date:
        query = query.filter(LeaveApplication.to_date <= to_date)

    if approver_uuid:
        approver = db.query(Employee).filter(Employee.uuid == approver_uuid).first()
        if approver:
            query = query.filter(LeaveApplication.current_approver_id == approver.id)
        else:
             return LeaveApplicationListResponse(
                success=True,
                message="Approver not found",
                data=[],
                pagination={"total_records": 0, "current_page": page, "total_pages": 0, "page_size": limit}
            )

    if search or sort_by == 'employee':
        query = query.join(Employee, LeaveApplication.employee_id == Employee.id)

    if search:
        search_term = f"%{search}%"
        query = query.filter(
            or_(
                Employee.first_name.ilike(search_term),
                Employee.last_name.ilike(search_term),
                Employee.employee_code.ilike(search_term)
            )
        )

    if sort_by == 'employee':
        if order == 'asc':
            query = query.order_by(Employee.first_name.asc(), Employee.last_name.asc())
        else:
            query = query.order_by(Employee.first_name.desc(), Employee.last_name.desc())
    else:
        if order == 'asc':
            query = query.order_by(LeaveApplication.created_at.asc())
        else:
            query = query.order_by(LeaveApplication.created_at.desc())

    # Pagination
    total_records = query.count()
    total_pages = (total_records + limit - 1) // limit
    skip = (page - 1) * limit

    applications = query.options(
        joinedload(LeaveApplication.employee),
        joinedload(LeaveApplication.leave_type),
        joinedload(LeaveApplication.current_approver),
        joinedload(LeaveApplication.approved_by_user),
        joinedload(LeaveApplication.rejected_by_user)
    ).offset(skip).limit(limit).all()

    pagination = {
        "total_records": total_records,
        "current_page": page,
        "total_pages": total_pages,
        "page_size": limit
    }

    return LeaveApplicationListResponse(
        success=True,
        message="Leave applications retrieved successfully",
        data=applications,
        pagination=pagination
    )

@router.post("/", response_model=LeaveApplicationResponse)
def apply_for_leave(
    employee_uuid: uuid.UUID = Form(...),
    leave_type_uuid: uuid.UUID = Form(...),
    from_date: date = Form(...),
    to_date: date = Form(...),
    reason: str = Form(...),
    is_half_day: bool = Form(False),
    half_day_session: Optional[str] = Form(None),
    reason_category: Optional[str] = Form(None),
    contact_address: Optional[str] = Form(None),
    contact_phone: Optional[str] = Form(None),
    remarks: Optional[str] = Form(None),
    compoff_application_uuids: Optional[List[uuid.UUID]] = Form(None),
    attachments: Optional[List[UploadFile]] = File(None),
    db: Session = Depends(deps.get_db),
    current_org: Organization = Depends(deps.get_current_org),
    current_user: Union[Organization, Employee] = Depends(deps.get_current_user)
):
    """
    Submit a new leave application.
    Calculates duration, checks for overlaps, and validates available balance.
    """
    # 1. Resolve Employee
    employee = db.query(Employee).filter(
        Employee.uuid == employee_uuid,
        Employee.organization_id == current_org.id
    ).first()
    
    if not employee:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Employee not found"
        )

    # RBAC Check: Employee can only apply for themselves
    if isinstance(current_user, Employee) and current_user.id != employee.id:
        if not deps.has_permission(db, current_user, "56"):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied. You can only apply for leave for yourself."
            )
        
    # 2. Resolve Leave Type
    leave_type = db.query(LeaveType).filter(
        LeaveType.uuid == leave_type_uuid,
        LeaveType.organization_id == current_org.id,
        LeaveType.is_deleted == False
    ).first()
    
    if not leave_type:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Leave type not found"
        )
        
    # 3. Calculate Total Days
    if is_half_day:
        total_days = Decimal('0.5')
    else:
        # Basic calculation: days = (to - from) + 1
        total_days = Decimal(str((to_date - from_date).days + 1))
        
    if total_days <= 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid leave period: end date is before start date."
        )

    # 4. Check for Overlapping Applications (PENDING or APPROVED)
    overlaps = db.query(LeaveApplication).filter(
        LeaveApplication.employee_id == employee.id,
        LeaveApplication.status.in_([LeaveStatus.PENDING, LeaveStatus.APPROVED]),
        or_(
            and_(LeaveApplication.from_date <= from_date, LeaveApplication.to_date >= from_date),
            and_(LeaveApplication.from_date <= to_date, LeaveApplication.to_date >= to_date),
            and_(LeaveApplication.from_date >= from_date, LeaveApplication.to_date <= to_date)
        )
    ).first()
    
    if overlaps:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Overlap detected with an existing {overlaps.status} leave ({overlaps.from_date} to {overlaps.to_date})"
        )

    if not compoff_application_uuids:
        balance = db.query(LeaveBalance).filter(
            LeaveBalance.employee_id == employee.id,
            LeaveBalance.leave_type_id == leave_type.id,
            LeaveBalance.balance_year == from_date.year
        ).first()
        
        if not balance:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No leave balance found for this year. Please contact HR."
            )
            
        if not leave_type.allow_negative_balance and (balance.available_balance < total_days):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Insufficient balance. Available: {balance.available_balance}, Requested: {total_days}"
            )
    else:
        # Validate Comp-off Stack
        comp_offs = db.query(CompensatoryOff).filter(
            CompensatoryOff.uuid.in_(compoff_application_uuids),
            CompensatoryOff.organization_id == current_org.id,
            CompensatoryOff.employee_id == employee.id
        ).order_by(CompensatoryOff.expiry_date.asc()).all()
        
        if not comp_offs:
            raise HTTPException(status_code=404, detail="Selected compensatory off credits not found.")
            
        total_comp_off_available = sum(c.remaining_days for c in comp_offs)
        
        # Mixed Deduction check: if comp-off doesn't cover all, check leave pool for remainder
        balance_needed_from_pool = max(Decimal('0'), total_days - total_comp_off_available)
        
        if balance_needed_from_pool > 0:
            balance = db.query(LeaveBalance).filter(
                LeaveBalance.employee_id == employee.id,
                LeaveBalance.leave_type_id == leave_type.id,
                LeaveBalance.balance_year == from_date.year
            ).first()
            
            if not balance:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Comp-off covers only {total_comp_off_available} days. No leave balance found for the remaining {balance_needed_from_pool} days."
                )
                
            if not leave_type.allow_negative_balance and (balance.available_balance < balance_needed_from_pool):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Insufficient combined balance. Comp-off: {total_comp_off_available}, Leave Pool: {balance.available_balance}. Total Requested: {total_days}"
                )
             
        for c in comp_offs:
            if c.is_expired or c.is_lapsed:
                raise HTTPException(status_code=400, detail=f"Credit earned on {c.worked_date} has expired.")

    # 6. Generate Application Number
    timestamp = datetime.utcnow().strftime("%Y%m%d%H%M%S")
    application_number = f"LV-{employee.employee_code}-{timestamp}"
    
    # 7. Determine Current Approver (Reporting Manager)
    current_approver_id = employee.reporting_manager_id
    
    # 8. Handle File Uploads
    attachment_paths = []
    if attachments:
        sub_path = f"{current_org.uuid}/leave_attachments/{employee.uuid}"
        for file in attachments:
            file_path = save_upload_file(file, sub_path)
            attachment_paths.append(file_path)

    # 9. Create Application
    application = LeaveApplication(
        organization_id=current_org.id,
        employee_id=employee.id,
        leave_type_id=leave_type.id,
        application_number=application_number,
        from_date=from_date,
        to_date=to_date,
        total_days=total_days,
        is_half_day=is_half_day,
        half_day_session=half_day_session,
        reason=reason,
        reason_category=reason_category,
        contact_address=contact_address,
        contact_phone=contact_phone,
        attachment_urls=attachment_paths,
        remarks=remarks,
        status=LeaveStatus.PENDING,
        current_approver_id=current_approver_id,
        is_comp_off=bool(compoff_application_uuids),
        comp_off_id=comp_offs[0].id if compoff_application_uuids else None # Linking to first as a primary reference
    )
    
    # 10. Utilize Comp-off Waterfall if applicable
    if compoff_application_uuids:
        remaining_to_utilize = total_days
        for c in comp_offs:
            if remaining_to_utilize <= 0:
                break
            
            utilize_amount = min(c.remaining_days, remaining_to_utilize)
            c.utilized_days += utilize_amount
            c.remaining_days -= utilize_amount
            c.utilized_date = date.today()
            if c.remaining_days <= 0:
                c.is_utilized = True
            
            remaining_to_utilize -= utilize_amount
    
    db.add(application)
    db.flush() # Get application.id before commit to link comp-off
    
    if compoff_application_uuids:
        for c in comp_offs:
             c.leave_application_id = application.id
        
    db.commit()
    db.refresh(application)
    
    # Reload with relationships
    application = db.query(LeaveApplication).filter(LeaveApplication.id == application.id).options(
        joinedload(LeaveApplication.employee),
        joinedload(LeaveApplication.leave_type),
        joinedload(LeaveApplication.current_approver)
    ).first()
    
    return LeaveApplicationResponse(
        success=True,
        message="Leave application submitted successfully",
        data=application
    )

@router.get("/{application_uuid}", response_model=LeaveApplicationResponse, dependencies=[Depends(deps.check_permission("55"))])
def get_leave_application(
    application_uuid: uuid.UUID,
    db: Session = Depends(deps.get_db),
    current_org: Organization = Depends(deps.get_current_org)
):
    """
    Retrieve details of a specific leave application, including its approval history.
    """
    from app.models.attendance import LeaveApprovalHistory
    
    application = db.query(LeaveApplication).filter(
        LeaveApplication.uuid == application_uuid,
        LeaveApplication.organization_id == current_org.id
    ).options(
        joinedload(LeaveApplication.employee),
        joinedload(LeaveApplication.leave_type),
        joinedload(LeaveApplication.current_approver),
        joinedload(LeaveApplication.approved_by_user),
        joinedload(LeaveApplication.rejected_by_user),
        joinedload(LeaveApplication.approval_history).joinedload(LeaveApprovalHistory.approver)
    ).first()
    
    if not application:
        return JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND,
            content={"success": False, "message": "Leave application not found", "data": None}
        )
        
    return LeaveApplicationResponse(
        success=True,
        message="Leave application retrieved successfully",
        data=application
    )

@router.put("/{application_uuid}", response_model=LeaveApplicationResponse)
def update_leave_application(
    application_uuid: uuid.UUID,
    leave_type_uuid: Optional[uuid.UUID] = Form(None),
    from_date: Optional[date] = Form(None),
    to_date: Optional[date] = Form(None),
    reason: Optional[str] = Form(None),
    is_half_day: Optional[bool] = Form(None),
    half_day_session: Optional[str] = Form(None),
    reason_category: Optional[str] = Form(None),
    contact_address: Optional[str] = Form(None),
    contact_phone: Optional[str] = Form(None),
    remarks: Optional[str] = Form(None),
    attachments: Optional[List[UploadFile]] = File(None),
    db: Session = Depends(deps.get_db),
    current_org: Organization = Depends(deps.get_current_org),
    current_user: Union[Organization, Employee] = Depends(deps.get_current_user)
):
    """
    Update an existing leave application.
    Can only be updated if status is DRAFT or PENDING.
    Recalculates duration and re-validates overlaps/balance if dates change.
    """
    application = db.query(LeaveApplication).filter(
        LeaveApplication.uuid == application_uuid,
        LeaveApplication.organization_id == current_org.id
    ).first()
    
    if not application:
        return JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND,
            content={"success": False, "message": "Leave application not found", "data": None}
        )
    
    # RBAC Check: Employee can only update their own application
    if isinstance(current_user, Employee) and current_user.id != application.employee_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied. You can only update your own leave applications."
        )
        
    if application.status not in [LeaveStatus.DRAFT, LeaveStatus.PENDING]:
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={"success": False, "message": f"Cannot update application in {application.status} status", "data": None}
        )

    # Track if we need to re-validate dates/balance
    needs_revalidation = False
    
    # 1. Update simple fields
    if reason is not None: application.reason = reason
    if reason_category is not None: application.reason_category = reason_category
    if contact_address is not None: application.contact_address = contact_address
    if contact_phone is not None: application.contact_phone = contact_phone
    if remarks is not None: application.remarks = remarks

    # 2. Handle File Uploads (Add to existing or replace?)
    # For consistency with POST (which creates a new set), we'll replace the attachments 
    # if new ones are provided. If one wants to KEEP old ones, they'd need a different mechanism
    # but based on "same as POST", replacement is often expected for the field.
    if attachments:
        sub_path = f"{current_org.uuid}/leave_attachments/{application.employee.uuid}"
        attachment_paths = []
        for file in attachments:
            file_path = save_upload_file(file, sub_path)
            attachment_paths.append(file_path)
        application.attachment_urls = attachment_paths

    # 3. Check if period or type changed
    if (from_date and from_date != application.from_date) or \
       (to_date and to_date != application.to_date) or \
       (is_half_day is not None and is_half_day != application.is_half_day) or \
       (leave_type_uuid and leave_type_uuid != application.leave_type.uuid):
        needs_revalidation = True

    if needs_revalidation:
        eff_from_date = from_date or application.from_date
        eff_to_date = to_date or application.to_date
        eff_is_half_day = is_half_day if is_half_day is not None else application.is_half_day
        
        # Resolve Leave Type
        if leave_type_uuid:
            leave_type = db.query(LeaveType).filter(
                LeaveType.uuid == leave_type_uuid,
                LeaveType.organization_id == current_org.id
            ).first()
            if not leave_type:
                return JSONResponse(
                    status_code=status.HTTP_404_NOT_FOUND,
                    content={"success": False, "message": "New leave type not found", "data": None}
                )
            application.leave_type_id = leave_type.id
        else:
            leave_type = application.leave_type

        # Re-calculate Duration
        if eff_is_half_day:
            total_days = 0.5
        else:
            total_days = (eff_to_date - eff_from_date).days + 1
            
        if total_days <= 0:
            return JSONResponse(
                status_code=status.HTTP_400_BAD_REQUEST,
                content={"success": False, "message": "Invalid leave period", "data": None}
            )

        # Check for Overlaps (excluding self)
        overlaps = db.query(LeaveApplication).filter(
            LeaveApplication.employee_id == application.employee_id,
            LeaveApplication.id != application.id,
            LeaveApplication.status.in_([LeaveStatus.PENDING, LeaveStatus.APPROVED]),
            or_(
                and_(LeaveApplication.from_date <= eff_from_date, LeaveApplication.to_date >= eff_from_date),
                and_(LeaveApplication.from_date <= eff_to_date, LeaveApplication.to_date >= eff_to_date),
                and_(LeaveApplication.from_date >= eff_from_date, LeaveApplication.to_date <= eff_to_date)
            )
        ).first()
        
        if overlaps:
            return JSONResponse(
                status_code=status.HTTP_400_BAD_REQUEST,
                content={"success": False, "message": f"Overlap detected with {overlaps.status} leave", "data": None}
            )

        # Check Balance
        balance = db.query(LeaveBalance).filter(
            LeaveBalance.employee_id == application.employee_id,
            LeaveBalance.leave_type_id == leave_type.id,
            LeaveBalance.balance_year == eff_from_date.year
        ).first()
        
        if not balance:
            return JSONResponse(
                status_code=status.HTTP_400_BAD_REQUEST,
                content={"success": False, "message": "No leave balance found for selected year", "data": None}
            )
            
        if not leave_type.allow_negative_balance and (balance.available_balance < total_days):
            return JSONResponse(
                status_code=status.HTTP_400_BAD_REQUEST,
                content={"success": False, "message": f"Insufficient balance. Available: {balance.available_balance}", "data": None}
            )

        # Apply updates
        application.from_date = eff_from_date
        application.to_date = eff_to_date
        application.is_half_day = eff_is_half_day
        application.total_days = total_days
        if half_day_session is not None:
            application.half_day_session = half_day_session

    db.commit()
    db.refresh(application)
    
    # Reload with relationships
    application = db.query(LeaveApplication).filter(LeaveApplication.id == application.id).options(
        joinedload(LeaveApplication.employee),
        joinedload(LeaveApplication.leave_type),
        joinedload(LeaveApplication.current_approver)
    ).first()
    
    return LeaveApplicationResponse(
        success=True,
        message="Leave application updated successfully",
        data=application
    )

@router.patch("/{application_uuid}/approve", response_model=LeaveApplicationResponse, dependencies=[Depends(deps.check_permission("57"))])
def approve_leave_application(
    application_uuid: uuid.UUID,
    action_in: LeaveActionRequest,
    db: Session = Depends(deps.get_db),
    current_org: Organization = Depends(deps.get_current_org)
):
    """
    Approve a leave application.
    Deducts the balance from the employee's leave ledger.
    """
    application = db.query(LeaveApplication).filter(
        LeaveApplication.uuid == application_uuid,
        LeaveApplication.organization_id == current_org.id
    ).first()
    
    if not application:
        return JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND,
            content={"success": False, "message": "Leave application not found", "data": None}
        )
        
    if application.status != LeaveStatus.PENDING:
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={"success": False, "message": f"Cannot approve application in {application.status} status", "data": None}
        )

    # 1. Update Application Status
    application.status = LeaveStatus.APPROVED
    application.approved_at = datetime.utcnow()
    # Setting approved_by to current_approver_id as we don't have individual user login context yet
    application.approved_by = application.current_approver_id 
    application.approver_comments = action_in.comments
    
    # 2. Update Balance if not already deducted
    if not application.balance_deducted:
        # Calculate how much was covered by Comp-Offs (already deducted in POST)
        covered_by_compoff = Decimal('0')
        if application.is_comp_off:
            covered_by_compoff = db.query(func.sum(CompensatoryOff.utilized_days)).filter(
                CompensatoryOff.leave_application_id == application.id
            ).scalar() or Decimal('0')
        
        remaining_to_deduct = max(Decimal('0'), application.total_days - covered_by_compoff)
        
        if remaining_to_deduct > 0:
            balance = db.query(LeaveBalance).filter(
                LeaveBalance.employee_id == application.employee_id,
                LeaveBalance.leave_type_id == application.leave_type_id,
                LeaveBalance.balance_year == application.from_date.year
            ).first()
            
            if balance:
                balance.used += remaining_to_deduct
                balance.available_balance -= remaining_to_deduct
                application.balance_deducted = True
                application.deducted_from_balance_id = balance.id
        else:
            # Fully covered by comp-off
            application.balance_deducted = True
    
    # 3. Record History
    history = LeaveApprovalHistory(
        leave_application_id=application.id,
        approval_level=application.approval_level + 1,
        approver_id=application.current_approver_id or 1,
        action="approved",
        comments=action_in.comments,
        action_date=datetime.utcnow()
    )
    db.add(history)
    
    db.commit()
    db.refresh(application)
    
    # Reload with relationships
    application = db.query(LeaveApplication).filter(LeaveApplication.id == application.id).options(
        joinedload(LeaveApplication.employee),
        joinedload(LeaveApplication.leave_type),
        joinedload(LeaveApplication.current_approver),
        joinedload(LeaveApplication.approval_history).joinedload(LeaveApprovalHistory.approver)
    ).first()
    
    return LeaveApplicationResponse(
        success=True,
        message="Leave application approved successfully",
        data=application
    )

@router.post("/bulk-approve", response_model=BulkLeaveApprovalResponse, dependencies=[Depends(deps.check_permission("57"))])
def bulk_approve_leave_applications(
    action_in: BulkLeaveApprovalRequest,
    db: Session = Depends(deps.get_db),
    current_org: Organization = Depends(deps.get_current_org)
):
    """
    Bulk approve multiple leave applications.
    """
    total = len(action_in.application_ids)
    success_count = 0
    errors = []
    
    for application_uuid in action_in.application_ids:
        try:
            application = db.query(LeaveApplication).filter(
                LeaveApplication.uuid == application_uuid,
                LeaveApplication.organization_id == current_org.id
            ).first()
            
            if not application:
                errors.append({"uuid": str(application_uuid), "error": "Application not found"})
                continue
                
            if application.status != LeaveStatus.PENDING:
                errors.append({"uuid": str(application_uuid), "error": f"Cannot approve application in {application.status} status"})
                continue

            # 1. Update Application Status
            application.status = LeaveStatus.APPROVED
            application.approved_at = datetime.utcnow()
            application.approved_by = application.current_approver_id 
            application.approver_comments = action_in.comments
            
            # 2. Update Balance if not already deducted
            if not application.balance_deducted:
                covered_by_compoff = Decimal('0')
                if application.is_comp_off:
                    covered_by_compoff = db.query(func.sum(CompensatoryOff.utilized_days)).filter(
                        CompensatoryOff.leave_application_id == application.id
                    ).scalar() or Decimal('0')
                
                remaining_to_deduct = max(Decimal('0'), application.total_days - covered_by_compoff)
                
                if remaining_to_deduct > 0:
                    balance = db.query(LeaveBalance).filter(
                        LeaveBalance.employee_id == application.employee_id,
                        LeaveBalance.leave_type_id == application.leave_type_id,
                        LeaveBalance.balance_year == application.from_date.year
                    ).first()
                    
                    if balance:
                        balance.used += remaining_to_deduct
                        balance.available_balance -= remaining_to_deduct
                        application.balance_deducted = True
                        application.deducted_from_balance_id = balance.id
                else:
                    application.balance_deducted = True
            
            # 3. Record History
            history = LeaveApprovalHistory(
                leave_application_id=application.id,
                approval_level=application.approval_level + 1,
                approver_id=application.current_approver_id or 1,
                action="approved",
                comments=action_in.comments,
                action_date=datetime.utcnow()
            )
            db.add(history)
            
            success_count += 1
            
        except Exception as e:
            db.rollback()
            errors.append({"uuid": str(application_uuid), "error": str(e)})
            continue

    if success_count > 0:
        try:
            db.commit()
        except Exception as e:
            db.rollback()
            return BulkLeaveApprovalResponse(
                success=False,
                message="Failed to commit bulk approval",
                data=BulkLeaveApprovalSummary(
                    total_records=total,
                    success_count=0,
                    error_count=total,
                    errors=[{"error": str(e)}]
                )
            )
            
    return BulkLeaveApprovalResponse(
        success=True,
        message=f"Bulk approval processed: {success_count} success, {len(errors)} errors",
        data=BulkLeaveApprovalSummary(
            total_records=total,
            success_count=success_count,
            error_count=len(errors),
            errors=errors
        )
    )

@router.post("/bulk-reject", response_model=BulkLeaveApprovalResponse, dependencies=[Depends(deps.check_permission("57"))])
def bulk_reject_leave_applications(
    action_in: BulkLeaveRejectRequest,
    db: Session = Depends(deps.get_db),
    current_org: Organization = Depends(deps.get_current_org)
):
    """
    Bulk reject multiple leave applications.
    """
    total = len(action_in.application_ids)
    success_count = 0
    errors = []
    
    for application_uuid in action_in.application_ids:
        try:
            application = db.query(LeaveApplication).filter(
                LeaveApplication.uuid == application_uuid,
                LeaveApplication.organization_id == current_org.id
            ).first()
            
            if not application:
                errors.append({"uuid": str(application_uuid), "error": "Application not found"})
                continue
                
            if application.status != LeaveStatus.PENDING:
                errors.append({"uuid": str(application_uuid), "error": f"Cannot reject application in {application.status} status"})
                continue

            # 1. Update Application Status
            application.status = LeaveStatus.REJECTED
            application.rejected_at = datetime.utcnow()
            application.rejected_by = application.current_approver_id
            application.rejection_reason = action_in.rejection_reason
            
            # 2. Record History
            history = LeaveApprovalHistory(
                leave_application_id=application.id,
                approval_level=application.approval_level + 1,
                approver_id=application.current_approver_id or 1,
                action="rejected",
                comments=action_in.rejection_reason,
                action_date=datetime.utcnow()
            )
            db.add(history)
            
            # 3. Refund Comp-off stack if applicable
            if application.is_comp_off:
                linked_comp_offs = db.query(CompensatoryOff).filter(CompensatoryOff.leave_application_id == application.id).all()
                for co in linked_comp_offs:
                    co.remaining_days += co.utilized_days
                    co.utilized_days = 0
                    co.is_utilized = False
                    co.leave_application_id = None
                    co.utilized_date = None
            
            success_count += 1
            
        except Exception as e:
            db.rollback()
            errors.append({"uuid": str(application_uuid), "error": str(e)})
            continue

    if success_count > 0:
        try:
            db.commit()
        except Exception as e:
            db.rollback()
            return BulkLeaveApprovalResponse(
                success=False,
                message="Failed to commit bulk rejection",
                data=BulkLeaveApprovalSummary(
                    total_records=total,
                    success_count=0,
                    error_count=total,
                    errors=[{"error": str(e)}]
                )
            )
            
    return BulkLeaveApprovalResponse(
        success=True,
        message=f"Bulk rejection processed: {success_count} success, {len(errors)} errors",
        data=BulkLeaveApprovalSummary(
            total_records=total,
            success_count=success_count,
            error_count=len(errors),
            errors=errors
        )
    )

@router.patch("/{application_uuid}/reject", response_model=LeaveApplicationResponse, dependencies=[Depends(deps.check_permission("57"))])
def reject_leave_application(
    application_uuid: uuid.UUID,
    action_in: LeaveActionRequest,
    db: Session = Depends(deps.get_db),
    current_org: Organization = Depends(deps.get_current_org)
):
    """
    Reject a leave application.
    """
    application = db.query(LeaveApplication).filter(
        LeaveApplication.uuid == application_uuid,
        LeaveApplication.organization_id == current_org.id
    ).first()
    
    if not application:
        return JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND,
            content={"success": False, "message": "Leave application not found", "data": None}
        )
        
    if application.status != LeaveStatus.PENDING:
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={"success": False, "message": f"Cannot reject application in {application.status} status", "data": None}
        )

    # 1. Update Application Status
    application.status = LeaveStatus.REJECTED
    application.rejected_at = datetime.utcnow()
    application.rejected_by = application.current_approver_id
    application.rejection_reason = action_in.comments
    
    # 2. Record History
    history = LeaveApprovalHistory(
        leave_application_id=application.id,
        approval_level=application.approval_level + 1,
        approver_id=application.current_approver_id or 1,
        action="rejected",
        comments=action_in.comments,
        action_date=datetime.utcnow()
    )
    db.add(history)
    
    # 3. Refund Comp-off stack if applicable
    if application.is_comp_off:
        linked_comp_offs = db.query(CompensatoryOff).filter(CompensatoryOff.leave_application_id == application.id).all()
        for comp_off in linked_comp_offs:
            # How many days were utilized for THIS application?
            # Since a Comp-off record can point to ONLY ONE leave application at a time in current schema
            # (only one utilized_days field, which reflects total utilized), 
            # and we are now supporting only one leave application per Comp-off record's 'current' utilization 
            # (or we'd need a separate mapping table).
            # ACTUALLY, if multiple records point to the same application, 
            # and we assume they were only utilized for this application during this transaction:
            # We restore the utilized_days and remaining_days.
            # But wait: utilized_days is cumulative? 
            # Let's check models again. 
            # utilized_days is total utilized. 
            # If we refund, we need to know how much was from THIS application.
            # Usually, total_days of leave = sum of all utilized chunks.
            # If we assume one Comp-off record is only used for ONE leave application at a time 
            # (which is typical for this HR logic), we can just restore fully.
            # Wait, the user's waterfall logic uses the FULL remaining balance of a record.
            # So the utilized_days for that record in THIS context is whatever was subtracted.
            
            # Since we set leave_application_id = application.id on all involved records:
            # We can use that link. 
            # But wait, if a record was partially utilized before? 
            # The current state only tracks latest leave_application_id.
            
            # For now, I'll follow the pattern: 
            # restored = utilised_days (assuming it was all for this app if it's the current link)
            # This is imperfect if credits are multi-use, but matches user's request for "refund".
            
            # Refined Refund:
            # Since we don't track chunks, we'll restore utilized_days to remaining.
            # WARNING: This assumes the records were dedicated to this application.
            comp_off.remaining_days += comp_off.utilized_days
            comp_off.utilized_days = 0
            comp_off.is_utilized = False
            comp_off.leave_application_id = None
            comp_off.utilized_date = None
    
    db.commit()
    db.refresh(application)
    
    # Reload with relationships
    application = db.query(LeaveApplication).filter(LeaveApplication.id == application.id).options(
        joinedload(LeaveApplication.employee),
        joinedload(LeaveApplication.leave_type),
        joinedload(LeaveApplication.current_approver),
        joinedload(LeaveApplication.approval_history).joinedload(LeaveApprovalHistory.approver)
    ).first()
    
    return LeaveApplicationResponse(
        success=True,
        message="Leave application rejected successfully",
        data=application
    )

@router.patch("/{application_uuid}/cancel", response_model=LeaveApplicationResponse, dependencies=[Depends(deps.check_permission("57"))])
def cancel_leave_application(
    application_uuid: uuid.UUID,
    action_in: LeaveActionRequest,
    db: Session = Depends(deps.get_db),
    current_org: Organization = Depends(deps.get_current_org)
):
    """
    Cancel a leave application.
    If already approved, reverts the balance deduction.
    """
    application = db.query(LeaveApplication).filter(
        LeaveApplication.uuid == application_uuid,
        LeaveApplication.organization_id == current_org.id
    ).first()
    
    if not application:
        return JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND,
            content={"success": False, "message": "Leave application not found", "data": None}
        )
        
    if application.status in [LeaveStatus.CANCELLED, LeaveStatus.REJECTED]:
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={"success": False, "message": f"Application is already {application.status}", "data": None}
        )

    # 1. Revert Balance if it was deducted (for already approved leaves)
    if application.status == LeaveStatus.APPROVED and application.balance_deducted:
        balance = db.query(LeaveBalance).filter(LeaveBalance.id == application.deducted_from_balance_id).first()
        if balance:
            covered_by_compoff = Decimal('0')
            if application.is_comp_off:
                covered_by_compoff = db.query(func.sum(CompensatoryOff.utilized_days)).filter(
                    CompensatoryOff.leave_application_id == application.id
                ).scalar() or Decimal('0')
            
            deducted_from_pool = max(Decimal('0'), application.total_days - covered_by_compoff)
            balance.used -= deducted_from_pool
            balance.available_balance += deducted_from_pool
            application.balance_deducted = False

    # 2. Update Application Status
    application.status = LeaveStatus.CANCELLED
    application.cancelled_at = datetime.utcnow()
    application.cancellation_reason = action_in.comments
    
    db.add(history)
    
    # 4. Refund Comp-off if applicable
    if application.is_comp_off and application.comp_off_id:
        comp_off = db.query(CompensatoryOff).filter(CompensatoryOff.id == application.comp_off_id).first()
        if comp_off:
            comp_off.utilized_days -= application.total_days
            comp_off.remaining_days += application.total_days
            comp_off.is_utilized = False
    
    db.commit()
    db.refresh(application)
    
    # Reload with relationships
    application = db.query(LeaveApplication).filter(LeaveApplication.id == application.id).options(
        joinedload(LeaveApplication.employee),
        joinedload(LeaveApplication.leave_type),
        joinedload(LeaveApplication.current_approver),
        joinedload(LeaveApplication.approval_history).joinedload(LeaveApprovalHistory.approver)
    ).first()
    
    return LeaveApplicationResponse(
        success=True,
        message="Leave application cancelled successfully",
        data=application
    )

@router.patch("/{application_uuid}/withdraw", response_model=LeaveApplicationResponse)
def withdraw_leave_application(
    application_uuid: uuid.UUID,
    action_in: Optional[LeaveActionRequest] = None,
    db: Session = Depends(deps.get_db),
    current_org: Organization = Depends(deps.get_current_org),
    current_user: Union[Organization, Employee] = Depends(deps.get_current_user)
):
    """
    Withdraw a leave application.
    Typically used by the employee before it is processed.
    If already approved, reverts the balance deduction.
    """
    application = db.query(LeaveApplication).filter(
        LeaveApplication.uuid == application_uuid,
        LeaveApplication.organization_id == current_org.id
    ).first()
    
    if not application:
        return JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND,
            content={"success": False, "message": "Leave application not found", "data": None}
        )

    # RBAC Check: Employee can only withdraw their own application
    if isinstance(current_user, Employee) and current_user.id != application.employee_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied. You can only withdraw your own leave applications."
        )
        
    if application.status in [LeaveStatus.WITHDRAWN, LeaveStatus.REJECTED, LeaveStatus.CANCELLED]:
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={"success": False, "message": f"Application is already {application.status}", "data": None}
        )

    # 1. Revert Balance if it was deducted
    if application.status == LeaveStatus.APPROVED and application.balance_deducted:
        balance = db.query(LeaveBalance).filter(LeaveBalance.id == application.deducted_from_balance_id).first()
        if balance:
            covered_by_compoff = Decimal('0')
            if application.is_comp_off:
                covered_by_compoff = db.query(func.sum(CompensatoryOff.utilized_days)).filter(
                    CompensatoryOff.leave_application_id == application.id
                ).scalar() or Decimal('0')
            
            deducted_from_pool = max(Decimal('0'), application.total_days - covered_by_compoff)
            balance.used -= deducted_from_pool
            balance.available_balance += deducted_from_pool
            application.balance_deducted = False

    # 2. Update Application Status
    application.status = LeaveStatus.WITHDRAWN
    # We use the same comment/remarks fields if provided
    if action_in and action_in.comments:
        application.remarks = action_in.comments
    
    db.add(history)
    
    # 3. Refund Comp-off stack if applicable
    if application.is_comp_off:
        linked_comp_offs = db.query(CompensatoryOff).filter(CompensatoryOff.leave_application_id == application.id).all()
        for co in linked_comp_offs:
            co.remaining_days += co.utilized_days
            co.utilized_days = 0
            co.is_utilized = False
            co.leave_application_id = None
            co.utilized_date = None
    
    db.commit()
    db.refresh(application)
    
    # Reload with relationships
    application = db.query(LeaveApplication).filter(LeaveApplication.id == application.id).options(
        joinedload(LeaveApplication.employee),
        joinedload(LeaveApplication.leave_type),
        joinedload(LeaveApplication.current_approver),
        joinedload(LeaveApplication.approval_history).joinedload(LeaveApprovalHistory.approver)
    ).first()
    
    return LeaveApplicationResponse(
        success=True,
        message="Leave application withdrawn successfully",
        data=application
    )

@router.post("/check-conflict", response_model=LeaveConflictCheckResponse)
def check_leave_conflict(
    check_in: LeaveConflictCheckRequest,
    db: Session = Depends(deps.get_db),
    current_org: Organization = Depends(deps.get_current_org)
):
    """
    Check if a leave application has any personal or team conflicts.
    """
    # 1. Resolve employee
    employee = db.query(Employee).filter(
        Employee.uuid == check_in.employee_uuid,
        Employee.organization_id == current_org.id
    ).first()
    
    if not employee:
        raise HTTPException(status_code=404, detail="Employee not found")

    # 2. Check personal conflicts (overlapping leaves)
    personal_conflicts = db.query(LeaveApplication).filter(
        LeaveApplication.employee_id == employee.id,
        LeaveApplication.status.in_([LeaveStatus.PENDING, LeaveStatus.APPROVED]),
        or_(
            and_(LeaveApplication.from_date <= check_in.from_date, LeaveApplication.to_date >= check_in.from_date),
            and_(LeaveApplication.from_date <= check_in.to_date, LeaveApplication.to_date >= check_in.to_date),
            and_(LeaveApplication.from_date >= check_in.from_date, LeaveApplication.to_date <= check_in.to_date)
        )
    ).all()

    # 3. Check team availability
    # We define team as people with the same reporting manager OR same department
    team_query = db.query(Employee).filter(
        Employee.organization_id == current_org.id,
        Employee.is_active == True
    )
    
    if employee.reporting_manager_id:
        team_query = team_query.filter(
            or_(
                Employee.reporting_manager_id == employee.reporting_manager_id,
                Employee.id == employee.reporting_manager_id
            )
        )
    elif employee.department_id:
        team_query = team_query.filter(Employee.department_id == employee.department_id)
    
    team_members = team_query.all()
    total_team_members = len(team_members)
    team_member_ids = [m.id for m in team_members if m.id != employee.id] # Exclude self for team check
    
    team_conflicts = db.query(LeaveApplication).filter(
        LeaveApplication.employee_id.in_(team_member_ids),
        LeaveApplication.status.in_([LeaveStatus.PENDING, LeaveStatus.APPROVED]),
        or_(
            and_(LeaveApplication.from_date <= check_in.from_date, LeaveApplication.to_date >= check_in.from_date),
            and_(LeaveApplication.from_date <= check_in.to_date, LeaveApplication.to_date >= check_in.to_date),
            and_(LeaveApplication.from_date >= check_in.from_date, LeaveApplication.to_date <= check_in.to_date)
        )
    ).options(joinedload(LeaveApplication.employee)).all()

    # Get unique employees on leave from team_conflicts
    employees_on_leave = {}
    for conflict in team_conflicts:
        employees_on_leave[conflict.employee_id] = conflict.employee
    
    members_on_leave = list(employees_on_leave.values())
    members_on_leave_count = len(members_on_leave)
    
    availability_percentage = 100.0
    if total_team_members > 0:
        availability_percentage = ((total_team_members - members_on_leave_count) / total_team_members) * 100

    return LeaveConflictCheckResponse(
        success=True,
        message="Conflict check completed",
        has_own_conflict=len(personal_conflicts) > 0,
        conflicting_applications=personal_conflicts,
        team_availability={
            "total_team_members": total_team_members,
            "members_on_leave_count": members_on_leave_count,
            "availability_percentage": round(availability_percentage, 2),
            "members_on_leave": members_on_leave
        }
    )
