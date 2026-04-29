import uuid
from typing import List, Optional, Union
from fastapi import APIRouter, Depends, Query, HTTPException, status
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import or_, and_
from datetime import datetime, date

from app.api import deps
from app.models.attendance import ShiftAssignment, ShiftMaster
from app.models.employee import Employee, Department
from app.models.organization import Organization
from app.schemas.attendance import (
    ShiftAssignmentSchema, ShiftAssignmentListResponse,
    BulkShiftAssignmentCreate, BulkShiftAssignmentResponse,
    ShiftAssignmentUpdate, ShiftAssignmentResponse
)

router = APIRouter()

@router.get("/", response_model=ShiftAssignmentListResponse)
def list_shift_assignments(
    db: Session = Depends(deps.get_db),
    current_user: Union[Organization, Employee] = Depends(deps.get_current_user),
    page: Optional[int] = Query(None, ge=1, description="Page number"),
    limit: int = Query(10, ge=1, description="Items per page"),
    employee_uuid: Optional[uuid.UUID] = Query(None, description="Filter by Employee UUID"),
    department_id: Optional[uuid.UUID] = Query(None, description="Filter by Department ID (UUID)"),
    department_uuid: Optional[uuid.UUID] = Query(None, description="Filter by Department UUID"),
    from_date: Optional[date] = Query(None, description="Filter by from date"),
    to_date: Optional[date] = Query(None, description="Filter by to date"),
    is_active: Optional[bool] = Query(None, description="Filter by Active Status"),
    sort_by: Optional[str] = Query("Recent", description="Sort by employee, department, shift, is_active, Oldest, Recent"),
    sort_order: Optional[str] = Query("desc", regex="^(asc|desc)$", description="Sort order (asc or desc)"),
    authorized: bool = Depends(deps.check_permission("29"))
):
    """
    List all shift assignments with filtering and pagination.
    """
    # RBAC logic: Employee without permission 29 can only see own assignments
    is_authorized_for_all = deps.has_permission(db, current_user, "29")
    current_org_id = current_user.id if isinstance(current_user, Organization) else current_user.organization_id
    
    query = db.query(ShiftAssignment).filter(
        ShiftAssignment.organization_id == current_org_id,
        ShiftAssignment.is_deleted == False
    )
    
    if isinstance(current_user, Employee) and not is_authorized_for_all:
        query = query.filter(ShiftAssignment.employee_id == current_user.id)
    
    # 1. Joins and Filtering
    joined_employee = False
    joined_department = False
    joined_shift = False

    # Consolidate department filters
    target_department_uuid = department_id or department_uuid
    
    if target_department_uuid:
        query = query.join(Employee, ShiftAssignment.employee_id == Employee.id)
        joined_employee = True
        query = query.join(Department, Employee.department_id == Department.id)
        joined_department = True
        query = query.filter(Department.uuid == target_department_uuid)
    
    if employee_uuid:
        # If we didn't join already
        if not joined_employee:
            query = query.join(Employee, ShiftAssignment.employee_id == Employee.id)
            joined_employee = True
        query = query.filter(Employee.uuid == employee_uuid)
        
    # 2. Additional Filters
    if is_active is not None:
        query = query.filter(ShiftAssignment.is_active == is_active)
        
    if from_date:
        query = query.filter(
            or_(
                ShiftAssignment.effective_to == None,
                ShiftAssignment.effective_to >= from_date
            )
        )
        
    if to_date:
        query = query.filter(ShiftAssignment.effective_from <= to_date)
        
    # 3. Advanced Sorting Logic
    allowed_sort_fields = {
        "employee": [Employee.first_name, Employee.last_name],
        "department": Department.department_name,
        "shift": ShiftMaster.shift_name,
        "is_active": ShiftAssignment.is_active,
        "Recent": ShiftAssignment.effective_from,
        "Oldest": ShiftAssignment.effective_from
    }

    # Handle special case for 'Oldest' and 'Recent' sort modes
    actual_sort_order = sort_order
    if sort_by == 'Oldest':
        actual_sort_order = 'asc'
    elif sort_by == 'Recent' or not sort_by:
        sort_by = 'Recent'
        # Default to desc for Recent if no specific order is requested
        if not sort_order:
             actual_sort_order = 'desc'

    if sort_by in allowed_sort_fields:
        # Ensure necessary tables are joined for sorting
        if sort_by == "employee" and not joined_employee:
            query = query.join(Employee, ShiftAssignment.employee_id == Employee.id)
            joined_employee = True
        elif sort_by == "department" and not joined_department:
            if not joined_employee:
                query = query.join(Employee, ShiftAssignment.employee_id == Employee.id)
                joined_employee = True
            query = query.join(Department, Employee.department_id == Department.id)
            joined_department = True
        elif sort_by == "shift" and not joined_shift:
            query = query.join(ShiftMaster, ShiftAssignment.shift_id == ShiftMaster.id)
            joined_shift = True

        sort_attr = allowed_sort_fields[sort_by]
        
        # Handle list of attributes (e.g., [first_name, last_name])
        if isinstance(sort_attr, list):
            for attr in sort_attr:
                query = query.order_by(attr.desc() if actual_sort_order == "desc" else attr.asc())
        else:
            query = query.order_by(sort_attr.desc() if actual_sort_order == "desc" else sort_attr.asc())
    else:
        # Fallback default: Recent (effective_from desc)
        query = query.order_by(ShiftAssignment.effective_from.desc())

    # Optimization: Early loading for response data
    query = query.options(
        joinedload(ShiftAssignment.employee),
        joinedload(ShiftAssignment.shift)
    )
    
    # 4. Pagination & Execution
    total_records = query.count()
    
    pagination_data = None
    if page is not None:
        total_pages = (total_records + limit - 1) // limit
        skip = (page - 1) * limit
        assignments = query.offset(skip).limit(limit).all()
        pagination_data = {
            "total_records": total_records,
            "current_page": page,
            "total_pages": total_pages,
            "page_size": limit
        }
    else:
        assignments = query.all()
        pagination_data = {
            "total_records": total_records,
            "current_page": 1,
            "total_pages": 1,
            "page_size": total_records if total_records > 0 else 0
        }
        
    if not assignments:
        return ShiftAssignmentListResponse(
            success=False,
            message="No shift assignments found"
        )
        
    return ShiftAssignmentListResponse(
        success=True,
        message="Shift assignments retrieved successfully",
        data=assignments,
        pagination=pagination_data
    )

@router.post("/", response_model=BulkShiftAssignmentResponse)
def create_shift_assignments(
    *,
    db: Session = Depends(deps.get_db),
    current_user: Union[Organization, Employee] = Depends(deps.get_current_user),
    assignment_in: BulkShiftAssignmentCreate,
    authorized: bool = Depends(deps.check_permission("30"))
):
    """
    Assign a shift to one or more employees.
    """
    current_org_id = current_user.id if isinstance(current_user, Organization) else current_user.organization_id
    # 1. Validate Shift exists and belongs to org
    shift = db.query(ShiftMaster).filter(
        ShiftMaster.uuid == assignment_in.shift_uuid,
        ShiftMaster.organization_id == current_org_id,
        ShiftMaster.is_deleted == False
    ).first()
    
    if not shift:
         return JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND,
            content={
                "success": False,
                "message": "Shift not found",
                "data": None
            }
        )

    # 2. Validate all Employees exist and belong to org
    employees = db.query(Employee).filter(
        Employee.uuid.in_(assignment_in.employee_uuids),
        Employee.organization_id == current_org_id
    ).all()
    
    if len(employees) != len(assignment_in.employee_uuids):
        found_uuids = [e.uuid for e in employees]
        missing_uuids = [str(u) for u in assignment_in.employee_uuids if u not in found_uuids]
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={
                "success": False,
                "message": f"Some employees were not found or do not belong to your organization: {', '.join(missing_uuids)}",
                "data": None
            }
        )

    # 3. Create Assignments
    created_assignments = []
    for employee in employees:
        # In a real-world scenario, you might want to auto-end any current active shift assignments
        # that overlap with this new start date. 
        
        db_assignment = ShiftAssignment(
            organization_id=current_org_id,
            employee_id=employee.id,
            shift_id=shift.id,
            effective_from=assignment_in.effective_from,
            effective_to=assignment_in.effective_to,
            is_rotating=assignment_in.is_rotating,
            rotation_pattern=assignment_in.rotation_pattern,
            is_active=assignment_in.is_active
        )
        db.add(db_assignment)
        created_assignments.append(db_assignment)
    
    try:
        db.commit()
        # Refresh to load relationships (employee, shift) for the response
        for assignment in created_assignments:
            db.refresh(assignment)
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An error occurred while creating shift assignments: {str(e)}"
        )
    
    return BulkShiftAssignmentResponse(
        success=True,
        message=f"Shift '{shift.shift_name}' assigned to {len(created_assignments)} employees successfully.",
        data=created_assignments
    )

@router.get("/{assignment_uuid}", response_model=ShiftAssignmentResponse)
def get_shift_assignment(
    assignment_uuid: uuid.UUID,
    db: Session = Depends(deps.get_db),
    current_user: Union[Organization, Employee] = Depends(deps.get_current_user),
    authorized: bool = Depends(deps.check_permission("29"))
):
    """
    Get shift assignment details.
    """
    current_org_id = current_user.id if isinstance(current_user, Organization) else current_user.organization_id
    assignment = db.query(ShiftAssignment).filter(
        ShiftAssignment.uuid == assignment_uuid,
        ShiftAssignment.organization_id == current_org_id,
        ShiftAssignment.is_deleted == False
    ).options(
        joinedload(ShiftAssignment.employee),
        joinedload(ShiftAssignment.shift)
    ).first()
    
    if not assignment:
        return JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND,
            content={
                "success": False,
                "message": "Shift assignment not found",
                "data": None
            }
        )
        
    return ShiftAssignmentResponse(
        success=True,
        message="Shift assignment retrieved successfully",
        data=assignment
    )

@router.put("/{assignment_uuid}", response_model=ShiftAssignmentResponse)
def update_shift_assignment(
    assignment_uuid: uuid.UUID,
    assignment_in: ShiftAssignmentUpdate,
    db: Session = Depends(deps.get_db),
    current_user: Union[Organization, Employee] = Depends(deps.get_current_user),
    authorized: bool = Depends(deps.check_permission("31"))
):
    """
    Update a shift assignment.
    """
    current_org_id = current_user.id if isinstance(current_user, Organization) else current_user.organization_id
    assignment = db.query(ShiftAssignment).filter(
        ShiftAssignment.uuid == assignment_uuid,
        ShiftAssignment.organization_id == current_org_id,
        ShiftAssignment.is_deleted == False
    ).first()
    
    if not assignment:
        return JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND,
            content={
                "success": False,
                "message": "Shift assignment not found",
                "data": None
            }
        )
    
    update_data = assignment_in.model_dump(exclude_unset=True)
    
    # If shift_uuid is being updated, validate the new shift
    if "shift_uuid" in update_data:
        new_shift = db.query(ShiftMaster).filter(
            ShiftMaster.uuid == update_data["shift_uuid"],
            ShiftMaster.organization_id == current_org_id,
            ShiftMaster.is_deleted == False
        ).first()
        
        if not new_shift:
            return JSONResponse(
                status_code=status.HTTP_400_BAD_REQUEST,
                content={
                    "success": False,
                    "message": "Invalid shift_uuid provided. Shift not found or belongs to another organization.",
                    "data": None
                }
            )
        # Update with internal ID
        assignment.shift_id = new_shift.id
        del update_data["shift_uuid"]
    
    # Update other fields
    for field, value in update_data.items():
        setattr(assignment, field, value)
    
    db.add(assignment)
    db.commit()
    db.refresh(assignment)
    
    return ShiftAssignmentResponse(
        success=True,
        message="Shift assignment updated successfully",
        data=assignment
    )

@router.delete("/{assignment_uuid}", response_model=ShiftAssignmentResponse)
def delete_shift_assignment(
    assignment_uuid: uuid.UUID,
    db: Session = Depends(deps.get_db),
    current_user: Union[Organization, Employee] = Depends(deps.get_current_user),
    authorized: bool = Depends(deps.check_permission("32"))
):
    """
    Soft delete a shift assignment.
    """
    current_org_id = current_user.id if isinstance(current_user, Organization) else current_user.organization_id
    assignment = db.query(ShiftAssignment).filter(
        ShiftAssignment.uuid == assignment_uuid,
        ShiftAssignment.organization_id == current_org_id,
        ShiftAssignment.is_deleted == False
    ).first()
    
    if not assignment:
        return JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND,
            content={
                "success": False,
                "message": "Shift assignment not found",
                "data": None
            }
        )
    
    # Perform soft delete
    assignment.is_deleted = True
    assignment.deleted_at = datetime.utcnow()
    assignment.is_active = False 
    
    db.add(assignment)
    db.commit()
    
    return ShiftAssignmentResponse(
        success=True,
        message="Shift assignment removed successfully",
        data=None
    )
