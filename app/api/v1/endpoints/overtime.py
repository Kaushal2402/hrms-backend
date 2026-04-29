import uuid
from typing import List, Optional, Union
from fastapi import APIRouter, Depends, HTTPException, status, Query
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import or_, func
from datetime import datetime, date, timedelta
from decimal import Decimal

from app.api import deps
from app.models.attendance import (
    OvertimeRequest, OvertimeStatus, AttendanceRecord, CompensationType
)
from app.models.employee import Employee, Department
from app.models.organization import Organization
from app.schemas.attendance import (
    OvertimeRequestListResponse, OvertimeRequestResponse,
    OvertimeRequestSchema, OvertimeRequestCreate, OvertimeRequestApproval,
    OvertimeRequestRejection
)

router = APIRouter()

@router.get("/requests", response_model=OvertimeRequestListResponse)
def list_overtime_requests(
    db: Session = Depends(deps.get_db),
    current_user: Union[Organization, Employee] = Depends(deps.get_current_user),
    page: Optional[int] = Query(None, ge=1, description="Page number"),
    limit: int = Query(10, ge=1, description="Items per page"),
    employee_uuid: Optional[uuid.UUID] = Query(None, description="Filter by Employee UUID"),
    approver_uuid: Optional[uuid.UUID] = Query(None, description="Filter by Approver UUID"),
    status: Optional[OvertimeStatus] = Query(None, description="Filter by Status"),
    from_date: Optional[date] = Query(None, description="Filter from attendance date"),
    to_date: Optional[date] = Query(None, description="Filter to attendance date"),
    sort_by: Optional[str] = Query(None, description="Sort by field"),
    order: Optional[str] = Query("desc", description="Sort order (asc/desc)"),
    search: Optional[str] = Query(None, description="Search term (Name or Code)"),
    department_uuid: Optional[uuid.UUID] = Query(None, description="Filter by Department UUID")
):
    """
    List overtime requests with filtering and pagination.
    """
    current_org_id = current_user.id if isinstance(current_user, Organization) else current_user.organization_id
    
    query = db.query(OvertimeRequest).filter(
        OvertimeRequest.organization_id == current_org_id
    )

    # 0. RBAC / Self-Service
    if not isinstance(current_user, Organization) and not deps.has_permission(db, current_user, "43"):
        # If no permission 43, only show own records
        query = query.filter(OvertimeRequest.employee_id == current_user.id)
    
    # 1. Joins & Filters
    if department_uuid:
        # Join Employee to filter by department
        dept = db.query(Department).filter(
            Department.uuid == department_uuid,
            Department.organization_id == current_org_id
        ).first()
        if dept:
            query = query.join(Employee, OvertimeRequest.employee_id == Employee.id).filter(
                Employee.department_id == dept.id
            )
        else:
            # If invalid dept UUID, return empty result
            query = query.filter(OvertimeRequest.id == -1)

    if employee_uuid:
        query = query.filter(OvertimeRequest.employee_id == db.query(Employee.id).filter(
            Employee.uuid == employee_uuid,
            Employee.organization_id == current_org_id
        ).scalar_subquery())
        
    if approver_uuid:
        query = query.filter(OvertimeRequest.approver_id == db.query(Employee.id).filter(
            Employee.uuid == approver_uuid,
            Employee.organization_id == current_org_id
        ).scalar_subquery())
        
    if search:
        search_term = f"%{search}%"
        # Ensure Employee is joined if not already
        if not department_uuid:
            query = query.join(Employee, OvertimeRequest.employee_id == Employee.id)
        
        query = query.filter(
            or_(
                Employee.first_name.ilike(search_term),
                Employee.last_name.ilike(search_term),
                Employee.employee_code.ilike(search_term)
            )
        )

    # 2. Other filters
    if status:
        query = query.filter(OvertimeRequest.status == status)
    if from_date:
        query = query.filter(OvertimeRequest.attendance_date >= from_date)
    if to_date:
        query = query.filter(OvertimeRequest.attendance_date <= to_date)
        
    # 3. Sorting
    sort_mapping = {
        "employee": [Employee.first_name, Employee.last_name],
        "attendance_date": [OvertimeRequest.attendance_date],
        "overtime_hours": [OvertimeRequest.overtime_hours],
        "compensation_type": [OvertimeRequest.compensation_type],
        "status": [OvertimeRequest.status]
    }
    
    # Ensure Employee is joined if sorting by employee
    if sort_by == "employee" and not department_uuid and not search:
        query = query.join(Employee, OvertimeRequest.employee_id == Employee.id)

    order_fields = sort_mapping.get(sort_by, [OvertimeRequest.attendance_date])
    
    if order.lower() == "asc":
        query = query.order_by(*[f.asc() for f in order_fields])
    else:
        query = query.order_by(*[f.desc() for f in order_fields])

    # 4. Optimization: Early loading
    query = query.options(
        joinedload(OvertimeRequest.employee),
        joinedload(OvertimeRequest.approver)
    )
    
    # 4. Pagination
    total_records = query.count()
    
    pagination_data = None
    if page is not None:
        total_pages = (total_records + limit - 1) // limit
        skip = (page - 1) * limit
        records = query.offset(skip).limit(limit).all()
        pagination_data = {
            "total_records": total_records,
            "current_page": page,
            "total_pages": total_pages,
            "page_size": limit
        }
    else:
        records = query.all()
        pagination_data = {
            "total_records": total_records,
            "current_page": 1,
            "total_pages": 1,
            "page_size": total_records
        }
        
    return OvertimeRequestListResponse(
        success=True,
        message="Overtime requests retrieved successfully",
        data=records,
        pagination=pagination_data
    )

@router.post("/requests", response_model=OvertimeRequestResponse)
def create_overtime_request(
    *,
    db: Session = Depends(deps.get_db),
    current_user: Union[Organization, Employee] = Depends(deps.get_current_user),
    overtime_in: OvertimeRequestCreate
):
    """
    Create a new overtime request.
    """
    current_org_id = current_user.id if isinstance(current_user, Organization) else current_user.organization_id
    
    # 0. RBAC / Self-Service
    if not isinstance(current_user, Organization) and not deps.has_permission(db, current_user, "44"):
        # Not Org and No Perm 44 -> Can only create for self
        if str(overtime_in.employee_uuid) != str(current_user.uuid):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You do not have permission (code 44) to create overtime for others."
            )

    # 1. Validate employee
    employee = db.query(Employee).filter(
        Employee.uuid == overtime_in.employee_uuid,
        Employee.organization_id == current_org_id
    ).first()
    
    if not employee:
        return JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND,
            content={"success": False, "message": "Employee not found", "data": None}
        )

    # 2. Check for existing attendance record
    attendance_record = db.query(AttendanceRecord).filter(
        AttendanceRecord.employee_id == employee.id,
        AttendanceRecord.attendance_date == overtime_in.attendance_date,
        AttendanceRecord.organization_id == current_org_id
    ).first()

    # 3. Calculate Overtime Hours
    duration = (overtime_in.overtime_end_time - overtime_in.overtime_start_time).total_seconds() / 3600.0
    if duration <= 0:
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={"success": False, "message": "Overtime end time must be after start time", "data": None}
        )
    
    overtime_hours = round(Decimal(str(duration)), 2)

    # 4. Create Overtime Request
    # Default approver is the reporting manager
    approver_id = employee.reporting_manager_id
    
    overtime = OvertimeRequest(
        organization_id=current_org_id,
        employee_id=employee.id,
        attendance_date=overtime_in.attendance_date,
        attendance_record_id=attendance_record.id if attendance_record else None,
        overtime_hours=overtime_hours,
        overtime_start_time=overtime_in.overtime_start_time,
        overtime_end_time=overtime_in.overtime_end_time,
        is_pre_approved=overtime_in.is_pre_approved,
        reason=overtime_in.reason,
        work_description=overtime_in.work_description,
        compensation_type=overtime_in.compensation_type,
        status=OvertimeStatus.PENDING,
        approver_id=approver_id
    )
    
    db.add(overtime)
    db.commit()
    db.refresh(overtime)
    
    return OvertimeRequestResponse(
        success=True,
        message="Overtime request created successfully",
        data=overtime
    )

@router.get("/requests/{overtime_uuid}", response_model=OvertimeRequestResponse)
def get_overtime_request(
    overtime_uuid: uuid.UUID,
    db: Session = Depends(deps.get_db),
    current_user: Union[Organization, Employee] = Depends(deps.get_current_user)
):
    """
    Get detailed information for a specific overtime request.
    """
    current_org_id = current_user.id if isinstance(current_user, Organization) else current_user.organization_id
    
    overtime = db.query(OvertimeRequest).filter(
        OvertimeRequest.uuid == overtime_uuid,
        OvertimeRequest.organization_id == current_org_id
    ).options(
        joinedload(OvertimeRequest.employee),
        joinedload(OvertimeRequest.approver),
        joinedload(OvertimeRequest.attendance_record)
    ).first()
    
    if not overtime:
        return JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND,
            content={"success": False, "message": "Overtime request not found", "data": None}
        )

    # RBAC / Self-Service
    if not isinstance(current_user, Organization) and not deps.has_permission(db, current_user, "43"):
        if overtime.employee_id != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You do not have permission to view other's overtime requests."
            )
        
    return OvertimeRequestResponse(
        success=True,
        message="Overtime request retrieved successfully",
        data=overtime
    )

@router.patch("/requests/{overtime_uuid}/approve", response_model=OvertimeRequestResponse)
def approve_overtime_request(
    overtime_uuid: uuid.UUID,
    approval_in: OvertimeRequestApproval,
    db: Session = Depends(deps.get_db),
    current_user: Union[Organization, Employee] = Depends(deps.get_current_user),
    _: bool = Depends(deps.check_permission("45"))
):
    """
    Approve an overtime request.
    """
    current_org_id = current_user.id if isinstance(current_user, Organization) else current_user.organization_id
    # 1. Fetch Request
    overtime = db.query(OvertimeRequest).filter(
        OvertimeRequest.uuid == overtime_uuid,
        OvertimeRequest.organization_id == current_org_id
    ).first()
    
    if not overtime:
        return JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND,
            content={"success": False, "message": "Overtime request not found", "data": None}
        )
        
    if overtime.status != OvertimeStatus.PENDING:
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={"success": False, "message": f"Request is already {overtime.status}", "data": None}
        )

    # 2. Update Request Status
    overtime.status = OvertimeStatus.APPROVED
    overtime.approver_comments = approval_in.comments
    overtime.approved_at = datetime.utcnow()
    
    if approval_in.compensation_type:
        overtime.compensation_type = approval_in.compensation_type
    
    # Optional logic: If compensation is comp_off, trigger comp-off generation
    # if overtime.compensation_type == 'comp_off':
    #     generate_comp_off(db, overtime)
    
    db.commit()
    db.refresh(overtime)
    
    return OvertimeRequestResponse(
        success=True,
        message="Overtime request approved successfully",
        data=overtime
    )

@router.patch("/requests/{overtime_uuid}/reject", response_model=OvertimeRequestResponse)
def reject_overtime_request(
    overtime_uuid: uuid.UUID,
    rejection_in: OvertimeRequestRejection,
    db: Session = Depends(deps.get_db),
    current_user: Union[Organization, Employee] = Depends(deps.get_current_user),
    _: bool = Depends(deps.check_permission("45"))
):
    """
    Reject an overtime request.
    """
    current_org_id = current_user.id if isinstance(current_user, Organization) else current_user.organization_id
    # 1. Fetch Request
    overtime = db.query(OvertimeRequest).filter(
        OvertimeRequest.uuid == overtime_uuid,
        OvertimeRequest.organization_id == current_org_id
    ).first()
    
    if not overtime:
        return JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND,
            content={"success": False, "message": "Overtime request not found", "data": None}
        )
        
    if overtime.status != OvertimeStatus.PENDING:
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={"success": False, "message": f"Request is already {overtime.status}", "data": None}
        )

    # 2. Update Request Status
    overtime.status = OvertimeStatus.REJECTED
    overtime.rejection_reason = rejection_in.rejection_reason
    
    db.commit()
    db.refresh(overtime)
    
    return OvertimeRequestResponse(
        success=True,
        message="Overtime request rejected successfully",
        data=overtime
    )
