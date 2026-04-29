import uuid
from typing import List, Optional, Union
from fastapi import APIRouter, Depends, Query, status
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import or_, and_
from datetime import date, timedelta

from app.api import deps
from app.models.attendance import ShiftRoster, ShiftMaster, ShiftAssignment
from app.models.employee import Employee, Department, Location
from app.models.organization import Organization
from app.schemas.attendance import (
    ShiftRosterSchema, ShiftRosterListResponse, ShiftRosterResponse,
    ShiftRosterUpdate, BulkShiftRosterCreate, BulkShiftRosterResponse,
    RosterGenerationRequest, RosterPublishRequest,
    SpecificRosterUnpublishRequest
)

router = APIRouter()

@router.get("/", response_model=ShiftRosterListResponse)
def list_shift_rosters(
    db: Session = Depends(deps.get_db),
    current_user: Union[Organization, Employee] = Depends(deps.get_current_user),
    page: Optional[int] = Query(None, ge=1, description="Page number"),
    limit: int = Query(10, ge=1, description="Items per page"),
    search: Optional[str] = Query(None, description="Search by employee name, employee code, or shift name"),
    employee_uuid: Optional[uuid.UUID] = Query(None, description="Filter by Employee UUID"),
    department_uuid: Optional[uuid.UUID] = Query(None, description="Filter by Department UUID"),
    location_uuid: Optional[uuid.UUID] = Query(None, description="Filter by Location UUID"),
    from_date: Optional[date] = Query(None, description="Filter from roster date"),
    to_date: Optional[date] = Query(None, description="Filter to roster date"),
    is_published: Optional[bool] = Query(None, description="Filter by Published Status"),
    authorized: bool = Depends(deps.check_permission("25"))
):
    """
    List daily shift roster records with filtering and pagination.
    """
    current_org_id = current_user.id if isinstance(current_user, Organization) else current_user.organization_id
    
    query = db.query(ShiftRoster).filter(
        ShiftRoster.organization_id == current_org_id,
        ShiftRoster.is_deleted == False
    )
    
    # 1. Joins for filtering
    needs_employee_join = department_uuid or location_uuid or employee_uuid or search
    
    if needs_employee_join:
        query = query.join(Employee, ShiftRoster.employee_id == Employee.id)

    if search:
        # Also join ShiftMaster to search by shift name
        query = query.join(ShiftMaster, ShiftRoster.shift_id == ShiftMaster.id)
        search_term = f"%{search}%"
        query = query.filter(
            or_(
                Employee.first_name.ilike(search_term),
                Employee.last_name.ilike(search_term),
                Employee.employee_code.ilike(search_term),
                ShiftMaster.shift_name.ilike(search_term),
            )
        )
        
    if department_uuid:
        query = query.join(Department, Employee.department_id == Department.id).filter(Department.uuid == department_uuid)
    
    if location_uuid:
        query = query.join(Location, Employee.location_id == Location.id).filter(Location.uuid == location_uuid)
        
    if employee_uuid:
        query = query.filter(Employee.uuid == employee_uuid)
        
    # 2. Date and Status Filters
    if from_date:
        query = query.filter(ShiftRoster.roster_date >= from_date)
    if to_date:
        query = query.filter(ShiftRoster.roster_date <= to_date)
    if is_published is not None:
        query = query.filter(ShiftRoster.is_published == is_published)
        
    # Optimization: Early loading
    query = query.options(
        joinedload(ShiftRoster.employee),
        joinedload(ShiftRoster.shift)
    ).order_by(ShiftRoster.roster_date.desc())
    
    # 3. Pagination & Execution
    total_records = query.count()
    
    pagination_data = None
    if page is not None:
        total_pages = (total_records + limit - 1) // limit
        skip = (page - 1) * limit
        rosters = query.offset(skip).limit(limit).all()
        pagination_data = {
            "total_records": total_records,
            "current_page": page,
            "total_pages": total_pages,
            "page_size": limit
        }
    else:
        rosters = query.all()
        pagination_data = {
            "total_records": total_records,
            "current_page": 1,
            "total_pages": 1,
            "page_size": total_records if total_records > 0 else 0
        }
        
    if not rosters:
        return ShiftRosterListResponse(
            success=False,
            message="No shift roster records found"
        )
        
    return ShiftRosterListResponse(
        success=True,
        message="Shift roster records retrieved successfully",
        data=rosters,
        pagination=pagination_data
    )

@router.get("/{roster_uuid}", response_model=ShiftRosterResponse)
def get_shift_roster(
    roster_uuid: uuid.UUID,
    db: Session = Depends(deps.get_db),
    current_user: Union[Organization, Employee] = Depends(deps.get_current_user),
    authorized: bool = Depends(deps.check_permission("25"))
):
    """
    Get details of a specific shift roster entry by UUID.
    """
    current_org_id = current_user.id if isinstance(current_user, Organization) else current_user.organization_id
    
    roster = db.query(ShiftRoster).filter(
        ShiftRoster.uuid == roster_uuid,
        ShiftRoster.organization_id == current_org_id,
        ShiftRoster.is_deleted == False
    ).options(
        joinedload(ShiftRoster.employee),
        joinedload(ShiftRoster.shift)
    ).first()
    
    if not roster:
         return JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND,
            content={"success": False, "message": "Shift roster entry not found", "data": None}
        )
        
    return ShiftRosterResponse(
        success=True,
        message="Shift roster details retrieved successfully",
        data=roster
    )

@router.put("/{roster_uuid}", response_model=ShiftRosterResponse)
def update_shift_roster(
    roster_uuid: uuid.UUID,
    roster_in: ShiftRosterUpdate,
    db: Session = Depends(deps.get_db),
    current_user: Union[Organization, Employee] = Depends(deps.get_current_user),
    authorized: bool = Depends(deps.check_permission("27"))
):
    """
    Update a specific shift roster entry by UUID.
    """
    current_org_id = current_user.id if isinstance(current_user, Organization) else current_user.organization_id
    
    roster = db.query(ShiftRoster).filter(
        ShiftRoster.uuid == roster_uuid,
        ShiftRoster.organization_id == current_org_id,
        ShiftRoster.is_deleted == False
    ).first()
    
    if not roster:
         return JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND,
            content={"success": False, "message": "Shift roster entry not found", "data": None}
        )
    
    update_data = roster_in.model_dump(exclude_unset=True)
    
    # Resolve employee_uuid if provided
    if "employee_uuid" in update_data:
        emp = db.query(Employee).filter(Employee.uuid == update_data["employee_uuid"], Employee.organization_id == current_org_id).first()
        if not emp:
             return JSONResponse(
                status_code=status.HTTP_400_BAD_REQUEST,
                content={"success": False, "message": "Invalid Employee UUID", "data": None}
            )
        roster.employee_id = emp.id
        del update_data["employee_uuid"]
        
    # Resolve shift_uuid if provided
    if "shift_uuid" in update_data:
        shift = db.query(ShiftMaster).filter(ShiftMaster.uuid == update_data["shift_uuid"], ShiftMaster.organization_id == current_org_id).first()
        if not shift:
             return JSONResponse(
                status_code=status.HTTP_400_BAD_REQUEST,
                content={"success": False, "message": "Invalid Shift UUID", "data": None}
            )
        roster.shift_id = shift.id
        del update_data["shift_uuid"]
        
    # Apply other fields
    for field, value in update_data.items():
        setattr(roster, field, value)
        
    try:
        db.commit()
        db.refresh(roster)
    except Exception as e:
        db.rollback()
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"success": False, "message": f"Error updating roster: {str(e)}", "data": None}
        )
        
    return ShiftRosterResponse(
        success=True,
        message="Shift roster updated successfully",
        data=roster
    )

@router.post("/generate", response_model=BulkShiftRosterResponse)
def generate_roster(
    *,
    db: Session = Depends(deps.get_db),
    current_user: Union[Organization, Employee] = Depends(deps.get_current_user),
    request_in: RosterGenerationRequest,
    authorized: bool = Depends(deps.check_permission("26"))
):
    """
    Auto-generate daily roster entries based on employees' shift assignments.
    """
    current_org_id = current_user.id if isinstance(current_user, Organization) else current_user.organization_id
    # 1. Fetch Employees
    emp_query = db.query(Employee).filter(Employee.organization_id == current_org_id)
    if request_in.department_uuid:
        emp_query = emp_query.join(Department).filter(Department.uuid == request_in.department_uuid)
    if request_in.location_uuid:
        emp_query = emp_query.join(Location).filter(Location.uuid == request_in.location_uuid)
    if request_in.employee_uuids:
        emp_query = emp_query.filter(Employee.uuid.in_(request_in.employee_uuids))
    
    employees = emp_query.all()
    if not employees:
         return JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND,
            content={"success": False, "message": "No employees found in the specified scope.", "data": None}
        )

    # 2. Iterate through dates and employees
    total_days = (request_in.to_date - request_in.from_date).days + 1
    processed_records = []
    
    # Pre-fetch all assignments for these employees in this range for optimization
    all_assignments = db.query(ShiftAssignment).filter(
        ShiftAssignment.employee_id.in_([e.id for e in employees]),
        ShiftAssignment.organization_id == current_org_id,
        ShiftAssignment.is_active == True,
        ShiftAssignment.is_deleted == False,
        or_(
            ShiftAssignment.effective_to == None,
            ShiftAssignment.effective_to >= request_in.from_date
        ),
        ShiftAssignment.effective_from <= request_in.to_date
    ).options(joinedload(ShiftAssignment.shift)).all()
    
    # Map assignments to employees for faster lookup
    emp_assignments = {}
    for assign in all_assignments:
        if assign.employee_id not in emp_assignments:
            emp_assignments[assign.employee_id] = []
        emp_assignments[assign.employee_id].append(assign)

    for i in range(total_days):
        current_date = request_in.from_date + timedelta(days=i)
        
        for employee in employees:
            # Find the active assignment for this specific date
            assignment = None
            for a in emp_assignments.get(employee.id, []):
                if a.effective_from <= current_date and (a.effective_to is None or a.effective_to >= current_date):
                    assignment = a
                    break
            
            if not assignment:
                continue
                
            # Check if roster record already exists
            existing = db.query(ShiftRoster).filter(
                ShiftRoster.employee_id == employee.id,
                ShiftRoster.roster_date == current_date,
                ShiftRoster.organization_id == current_org_id,
                ShiftRoster.is_deleted == False
            ).first()
            
            if existing and not request_in.overwrite_existing:
                continue
            
            # Week-off check
            is_week_off = False
            if assignment.shift.week_off_days:
                roster_weekday = (current_date.weekday() + 1) % 7 # 0=Sunday mapping
                if roster_weekday in assignment.shift.week_off_days:
                    is_week_off = True

            if existing:
                existing.shift_id = assignment.shift_id
                existing.is_week_off = is_week_off
                existing.is_published = request_in.publish_immediately
                db.add(existing)
                processed_records.append(existing)
            else:
                new_entry = ShiftRoster(
                    organization_id=current_org_id,
                    employee_id=employee.id,
                    shift_id=assignment.shift_id,
                    roster_date=current_date,
                    is_week_off=is_week_off,
                    is_published=request_in.publish_immediately,
                    uuid=uuid.uuid4()
                )
                db.add(new_entry)
                processed_records.append(new_entry)

    try:
        db.commit()
    except Exception as e:
        db.rollback()
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"success": False, "message": f"An error occurred: {str(e)}", "data": None}
        )
    
    # Return first 50 records to show success without overwhelming response
    return BulkShiftRosterResponse(
        success=True,
        message=f"Successfully generated {len(processed_records)} roster entries for {len(employees)} employees.",
        data=processed_records[:50]
    )

@router.patch("/publish", response_model=BulkShiftRosterResponse)
def publish_roster(
    *,
    db: Session = Depends(deps.get_db),
    current_user: Union[Organization, Employee] = Depends(deps.get_current_user),
    request_in: RosterPublishRequest,
    authorized: bool = Depends(deps.check_permission("27"))
):
    """
    Publish multiple daily shift roster records (make them visible to employees).
    """
    current_org_id = current_user.id if isinstance(current_user, Organization) else current_user.organization_id
    # 1. Base query for roster entries in date range
    query = db.query(ShiftRoster).filter(
        ShiftRoster.organization_id == current_org_id,
        ShiftRoster.is_deleted == False,
        ShiftRoster.roster_date >= request_in.from_date,
        ShiftRoster.roster_date <= request_in.to_date
    )

    # 2. Add filters for employee, department, location
    needs_employee_join = request_in.department_uuid or request_in.location_uuid or request_in.employee_uuids
    
    if needs_employee_join:
        query = query.join(Employee, ShiftRoster.employee_id == Employee.id)
        
    if request_in.department_uuid:
        query = query.join(Department, Employee.department_id == Department.id).filter(Department.uuid == request_in.department_uuid)
    
    if request_in.location_uuid:
        query = query.join(Location, Employee.location_id == Location.id).filter(Location.uuid == request_in.location_uuid)
        
    if request_in.employee_uuids:
        query = query.filter(Employee.uuid.in_(request_in.employee_uuids))

    # 3. Execute update
    records_to_publish = query.all()
    
    if not records_to_publish:
        return JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND,
            content={
                "success": False,
                "message": "No roster records found in the specified range/scope to publish.",
                "data": []
            }
        )

    for record in records_to_publish:
        record.is_published = True
        db.add(record)
    
    try:
        db.commit()
        # Refresh for response (optional, but good for consistency)
        for record in records_to_publish[:50]:
            db.refresh(record)
    except Exception as e:
        db.rollback()
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"success": False, "message": f"Error publishing roster: {str(e)}", "data": None}
        )

    return BulkShiftRosterResponse(
        success=True,
        message=f"Successfully published {len(records_to_publish)} roster entries.",
        data=records_to_publish[:50]
    )

@router.patch("/unpublish", response_model=BulkShiftRosterResponse)
def unpublish_specific_rosters(
    *,
    db: Session = Depends(deps.get_db),
    current_user: Union[Organization, Employee] = Depends(deps.get_current_user),
    request_in: SpecificRosterUnpublishRequest,
    authorized: bool = Depends(deps.check_permission("27"))
):
    """
    Unpublish specific daily shift roster records by their UUIDs.
    """
    current_org_id = current_user.id if isinstance(current_user, Organization) else current_user.organization_id
    
    records_to_unpublish = db.query(ShiftRoster).filter(
        ShiftRoster.organization_id == current_org_id,
        ShiftRoster.is_deleted == False,
        ShiftRoster.uuid.in_(request_in.roster_uuids)
    ).all()
    
    if not records_to_unpublish:
        return JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND,
            content={
                "success": False,
                "message": "No roster records found for the provided UUIDs to unpublish.",
                "data": []
            }
        )

    for record in records_to_unpublish:
        record.is_published = False
        db.add(record)
    
    try:
        db.commit()
    except Exception as e:
        db.rollback()
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"success": False, "message": f"Error unpublishing rosters: {str(e)}", "data": None}
        )

    return BulkShiftRosterResponse(
        success=True,
        message=f"Successfully unpublished {len(records_to_unpublish)} roster entries.",
        data=records_to_unpublish[:50]
    )

@router.patch("/bulk-unpublish", response_model=BulkShiftRosterResponse)
def bulk_unpublish_roster(
    *,
    db: Session = Depends(deps.get_db),
    current_user: Union[Organization, Employee] = Depends(deps.get_current_user),
    request_in: RosterPublishRequest,
    authorized: bool = Depends(deps.check_permission("27"))
):
    """
    Unpublish multiple daily shift roster records based on filters (date range, employee, etc).
    """
    current_org_id = current_user.id if isinstance(current_user, Organization) else current_user.organization_id
    # 1. Base query for roster entries in date range
    query = db.query(ShiftRoster).filter(
        ShiftRoster.organization_id == current_org_id,
        ShiftRoster.is_deleted == False,
        ShiftRoster.roster_date >= request_in.from_date,
        ShiftRoster.roster_date <= request_in.to_date
    )

    # 2. Add filters for employee, department, location
    needs_employee_join = request_in.department_uuid or request_in.location_uuid or request_in.employee_uuids
    
    if needs_employee_join:
        query = query.join(Employee, ShiftRoster.employee_id == Employee.id)
        
    if request_in.department_uuid:
        query = query.join(Department, Employee.department_id == Department.id).filter(Department.uuid == request_in.department_uuid)
    
    if request_in.location_uuid:
        query = query.join(Location, Employee.location_id == Location.id).filter(Location.uuid == request_in.location_uuid)
        
    if request_in.employee_uuids:
        query = query.filter(Employee.uuid.in_(request_in.employee_uuids))

    # 3. Execute update
    records_to_unpublish = query.all()
    
    if not records_to_unpublish:
        return JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND,
            content={
                "success": False,
                "message": "No roster records found in the specified range/scope to unpublish.",
                "data": []
            }
        )

    for record in records_to_unpublish:
        record.is_published = False
        db.add(record)
    
    try:
        db.commit()
    except Exception as e:
        db.rollback()
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"success": False, "message": f"Error unpublishing roster: {str(e)}", "data": None}
        )

    return BulkShiftRosterResponse(
        success=True,
        message=f"Successfully unpublished {len(records_to_unpublish)} roster entries.",
        data=records_to_unpublish[:50]
    )

@router.post("/", response_model=BulkShiftRosterResponse)
def upsert_shift_rosters(
    *,
    db: Session = Depends(deps.get_db),
    current_user: Union[Organization, Employee] = Depends(deps.get_current_user),
    roster_in: BulkShiftRosterCreate,
    authorized: bool = Depends(deps.check_permission("26"))
):
    """
    Create or update multiple daily shift roster records.
    """
    current_org_id = current_user.id if isinstance(current_user, Organization) else current_user.organization_id
    # 1. Collect all unique employee and shift UUIDs
    employee_uuids = {entry.employee_uuid for entry in roster_in.entries}
    shift_uuids = {entry.shift_uuid for entry in roster_in.entries}
    
    # 2. Fetch employees and shifts to map UUID -> ID
    employees = db.query(Employee).filter(
        Employee.uuid.in_(employee_uuids),
        Employee.organization_id == current_org_id
    ).all()
    
    shifts = db.query(ShiftMaster).filter(
        ShiftMaster.uuid.in_(shift_uuids),
        ShiftMaster.organization_id == current_org_id,
        ShiftMaster.is_deleted == False
    ).all()
    
    emp_map = {e.uuid: e.id for e in employees}
    shift_map = {s.uuid: s.id for s in shifts}
    
    # Validation
    if len(emp_map) != len(employee_uuids):
        missing = [str(u) for u in employee_uuids if u not in emp_map]
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={"success": False, "message": f"Employees not found: {', '.join(missing)}", "data": None}
        )
        
    if len(shift_map) != len(shift_uuids):
        missing = [str(u) for u in shift_uuids if u not in shift_map]
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={"success": False, "message": f"Shifts not found or deleted: {', '.join(missing)}", "data": None}
        )

    processed_rosters = []
    
    # 3. Process entries
    for entry in roster_in.entries:
        emp_id = emp_map[entry.employee_uuid]
        
        # Check if record already exists for this employee and date
        existing_roster = db.query(ShiftRoster).filter(
            ShiftRoster.employee_id == emp_id,
            ShiftRoster.roster_date == entry.roster_date,
            ShiftRoster.organization_id == current_org_id,
            ShiftRoster.is_deleted == False
        ).first()
        
        if existing_roster:
            # Update existing
            update_data = entry.model_dump(exclude={"employee_uuid", "shift_uuid"})
            for field, value in update_data.items():
                setattr(existing_roster, field, value)
            existing_roster.shift_id = shift_map[entry.shift_uuid]
            db.add(existing_roster)
            processed_rosters.append(existing_roster)
        else:
            # Create new
            new_roster = ShiftRoster(
                **entry.model_dump(exclude={"employee_uuid", "shift_uuid"}),
                organization_id=current_org_id,
                employee_id=emp_id,
                shift_id=shift_map[entry.shift_uuid]
            )
            db.add(new_roster)
            processed_rosters.append(new_roster)
            
    try:
        db.commit()
        # Refresh to load relationships for response
        for roster in processed_rosters:
            db.refresh(roster)
    except Exception as e:
        db.rollback()
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"success": False, "message": f"Error saving roster: {str(e)}", "data": None}
        )
        
    return BulkShiftRosterResponse(
        success=True,
        message=f"Successfully processed {len(processed_rosters)} roster entries.",
        data=processed_rosters
    )
