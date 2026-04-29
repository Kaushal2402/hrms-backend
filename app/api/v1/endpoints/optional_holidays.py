from datetime import date, datetime
from typing import List, Optional, Union
from sqlalchemy import or_, and_
from fastapi import APIRouter, Depends, Query, HTTPException, status
from sqlalchemy.orm import Session

from app.api import deps
from app.models.attendance import Holiday, HolidayType, OptionalHolidaySelection
from app.models.employee import Employee
from app.models.organization import Organization
from app.schemas.holiday import (
    HolidayListResponse, OptionalHolidaySelect, OptionalHolidaySelectionResponse,
    BulkOptionalHolidaySelect, BulkOptionalHolidaySelectionResponse, HolidayImportError
)

router = APIRouter()

@router.get("/", response_model=HolidayListResponse)
def list_optional_holidays(
    db: Session = Depends(deps.get_db),
    current_org: Organization = Depends(deps.get_current_org),
    current_user: Union[Organization, Employee] = Depends(deps.get_current_user),
    authorized: bool = Depends(deps.check_permission("59")),
    year: Optional[int] = Query(None, description="Filter by year (YYYY)"),
    location_id: Optional[int] = Query(None, description="Filter by location ID"),
    search: Optional[str] = Query(None, description="Search by name"),
    sort_by: str = Query("holiday_date", description="Sort by: holiday_name, holiday_date"),
    order: str = Query("asc", description="Sort order: asc, desc"),
    page: int = Query(1, ge=1, description="Page number"),
    limit: int = Query(10, ge=1, description="Items per page")
):
    """
    Retrieve a list of optional/restricted holidays.
    """
    # 1. Base Query
    query = db.query(Holiday).filter(
        Holiday.organization_id == current_org.id,
        Holiday.is_deleted == False,
        or_(
            Holiday.holiday_type == HolidayType.OPTIONAL,
            Holiday.holiday_type == HolidayType.RESTRICTED
        )
    )

    # 2. Filters
    if year:
        query = query.filter(Holiday.holiday_year == year)
    
    if location_id:
        from sqlalchemy import func
        query = query.filter(
            or_(
                Holiday.is_location_specific == False,
                func.json_contains(Holiday.location_ids, func.cast(location_id, func.JSON))
            )
        )

    if search:
        search_term = f"%{search}%"
        query = query.filter(Holiday.holiday_name.ilike(search_term))

    # 3. Sorting
    sort_column = getattr(Holiday, sort_by, Holiday.holiday_date)
    if order.lower() == "desc":
        query = query.order_by(sort_column.desc())
    else:
        query = query.order_by(sort_column.asc())

    # 4. Pagination
    total_records = query.count()
    total_pages = (total_records + limit - 1) // limit
    skip = (page - 1) * limit
    holidays = query.offset(skip).limit(limit).all()

    # 5. Resolve Scoping Names for Response
    from app.models.employee import Location, Department
    location_ids_all = set()
    department_ids_all = set()
    for h in holidays:
        if h.location_ids: location_ids_all.update(h.location_ids)
        if h.department_ids: department_ids_all.update(h.department_ids)
    
    location_map = {}
    if location_ids_all:
        locs = db.query(Location).filter(Location.id.in_(list(location_ids_all))).all()
        location_map = {l.id: {"uuid": l.uuid, "location_name": l.location_name} for l in locs}
        
    department_map = {}
    if department_ids_all:
        depts = db.query(Department).filter(Department.id.in_(list(department_ids_all))).all()
        department_map = {d.id: {"uuid": d.uuid, "department_name": d.department_name} for d in depts}
        
    for h in holidays:
        h.locations = [location_map[lid] for lid in h.location_ids if lid in location_map] if h.location_ids else []
        h.departments = [department_map[did] for did in h.department_ids if did in department_map] if h.department_ids else []

    # 6. Resolve Applied Employees
    holiday_ids = [h.id for h in holidays]
    employee_selections = db.query(
        OptionalHolidaySelection.holiday_id,
        Employee.uuid,
        Employee.first_name,
        Employee.last_name
    ).join(Employee, OptionalHolidaySelection.employee_id == Employee.id).filter(
        OptionalHolidaySelection.holiday_id.in_(holiday_ids)
    ).all()
    
    # Map employees to holidays
    emp_lookup = {}
    for h_id, emp_uuid, f_name, l_name in employee_selections:
        if h_id not in emp_lookup: emp_lookup[h_id] = []
        full_name = f"{f_name} {l_name}"
        emp_lookup[h_id].append({"uuid": emp_uuid, "full_name": full_name})
        
    for h in holidays:
        h.applied_employees = emp_lookup.get(h.id, [])

    return HolidayListResponse(
        success=True,
        message="Optional holidays retrieved successfully",
        data=holidays,
        pagination={
            "total_records": total_records,
            "current_page": page,
            "total_pages": total_pages,
            "page_size": limit
        }
    )

@router.post("/select", response_model=BulkOptionalHolidaySelectionResponse)
def select_optional_holiday(
    selection_in: BulkOptionalHolidaySelect,
    db: Session = Depends(deps.get_db),
    current_org: Organization = Depends(deps.get_current_org),
    current_user: Union[Organization, Employee] = Depends(deps.get_current_user),
    authorized: bool = Depends(deps.check_permission("60"))
):
    """
    Assign an optional or restricted holiday to one or more employees.
    Supports single or multiple assignments in the same batch.
    """
    # 1. Resolve Holiday
    holiday = db.query(Holiday).filter(
        Holiday.uuid == selection_in.holiday_uuid,
        Holiday.organization_id == current_org.id,
        Holiday.is_deleted == False
    ).first()

    if not holiday:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Holiday not found"
        )

    if holiday.holiday_type not in [HolidayType.OPTIONAL, HolidayType.RESTRICTED]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="This is a mandatory public holiday and does not require selection."
        )

    # 1. Resolve Target Employees
    target_employees = db.query(Employee).filter(
        Employee.uuid.in_(selection_in.employee_uuids),
        Employee.organization_id == current_org.id,
        Employee.is_deleted == False
    ).all()
    
    target_emp_map = {e.uuid: e.id for e in target_employees}
    target_emp_ids = set(target_emp_map.values())
    
    # 2. Validation: Capacity
    if holiday.is_restricted and holiday.max_employees_allowed:
        if len(target_emp_ids) > holiday.max_employees_allowed:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"This selection exceeds the maximum capacity of {holiday.max_employees_allowed} allowed for this holiday."
            )

    # 3. Track Outcome
    total_processed = len(selection_in.employee_uuids)
    errors = []
    for uuid_val in selection_in.employee_uuids:
        if uuid_val not in target_emp_map:
            errors.append(HolidayImportError(row=0, name=str(uuid_val), error="Employee not found or inactive"))

    failed_count = len(errors)
    
    # 4. Sync Selections
    # Fetch current state
    current_selections = db.query(OptionalHolidaySelection).filter(
        OptionalHolidaySelection.holiday_id == holiday.id
    ).all()
    current_emp_ids = {s.employee_id for s in current_selections}
    
    # Remove existing ones that are not in the new list
    removed_count = 0
    for s in current_selections:
        if s.employee_id not in target_emp_ids:
            db.delete(s)
            removed_count += 1
            
    # Add new ones that weren't there before
    added_count = 0
    for emp_id in target_emp_ids:
        if emp_id not in current_emp_ids:
            selection = OptionalHolidaySelection(
                employee_id=emp_id,
                holiday_id=holiday.id,
                selection_year=holiday.holiday_year,
                selected_at=datetime.utcnow()
            )
            db.add(selection)
            added_count += 1
            
    # 5. Update Holiday Counter
    holiday.employees_applied = len(target_emp_ids)

    try:
        db.commit()
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to synchronize selections: {str(e)}"
        )

    return BulkOptionalHolidaySelectionResponse(
        success=True,
        message=f"Sync completed. Added {added_count}, Removed {removed_count}. Total currently assigned: {holiday.employees_applied}.",
        total_processed=total_processed,
        successful_count=len(target_emp_ids),
        failed_count=failed_count,
        errors=errors
    )
