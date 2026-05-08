import uuid
from datetime import date, datetime
from typing import List, Optional
from fastapi import APIRouter, Depends, Query, status
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import or_, and_

from app.api import deps
from app.models.attendance import LeaveApplication, LeaveType, LeaveStatus, Holiday
from app.models.employee import Employee, Department, Location
from app.models.organization import Organization
from app.schemas.leave import LeaveCalendarResponse, LeaveCalendarEvent, HolidayCalendarEvent, LeaveCalendarData

router = APIRouter()

@router.get("/", response_model=LeaveCalendarResponse)
def get_leave_calendar(
    db: Session = Depends(deps.get_db),
    current_org: Organization = Depends(deps.get_current_org),
    from_date: Optional[date] = Query(None, description="Start date of the calendar range"),
    to_date: Optional[date] = Query(None, description="End date of the calendar range"),
    department_uuid: Optional[uuid.UUID] = Query(None, description="Filter by department UUID"),
    location_uuid: Optional[uuid.UUID] = Query(None, description="Filter by location UUID"),
    # team_id excluded for now as it's not present in Employee model
):
    """
    Get leave applications for calendar view within a date range and filters.
    """
    # 1. Base Query - Joining explicitly on employee_id to avoid AmbiguousForeignKeysError
    query = db.query(LeaveApplication).join(
        Employee, LeaveApplication.employee_id == Employee.id
    ).filter(
        LeaveApplication.organization_id == current_org.id,
        LeaveApplication.status.in_([LeaveStatus.PENDING, LeaveStatus.APPROVED])
    )

    # 2. Date Range Filter
    if from_date and to_date:
        # Leaves that overlap with the requested range
        query = query.filter(
            or_(
                and_(LeaveApplication.from_date <= from_date, LeaveApplication.to_date >= from_date),
                and_(LeaveApplication.from_date <= to_date, LeaveApplication.to_date >= to_date),
                and_(LeaveApplication.from_date >= from_date, LeaveApplication.to_date <= to_date)
            )
        )
    elif from_date:
        query = query.filter(LeaveApplication.to_date >= from_date)
    elif to_date:
        query = query.filter(LeaveApplication.from_date <= to_date)

    # 5. Holiday Query
    holiday_query = db.query(Holiday).filter(
        Holiday.organization_id == current_org.id,
        Holiday.is_active == True,
        Holiday.is_deleted == False
    )

    if from_date and to_date:
        holiday_query = holiday_query.filter(
            Holiday.holiday_date >= from_date,
            Holiday.holiday_date <= to_date
        )
    elif from_date:
        holiday_query = holiday_query.filter(Holiday.holiday_date >= from_date)
    elif to_date:
        holiday_query = holiday_query.filter(Holiday.holiday_date <= to_date)

    # Resolve IDs for Holiday filtering if needed
    dept_id = None
    if department_uuid:
        dept = db.query(Department).filter(Department.uuid == department_uuid).first()
        if dept:
            dept_id = dept.id
            query = query.filter(Employee.department_id == dept_id) # Already filtered above but being safe

    loc_id = None
    if location_uuid:
        loc = db.query(Location).filter(Location.uuid == location_uuid).first()
        if loc:
            loc_id = loc.id
            query = query.filter(Employee.location_id == loc_id) # Already filtered above but being safe

    # 6. Fetch Results
    applications = query.options(
        joinedload(LeaveApplication.employee),
        joinedload(LeaveApplication.leave_type)
    ).all()

    holidays = holiday_query.all()

    # Filter holidays based on location/department if applicable
    filtered_holidays = []
    for h in holidays:
        keep = True
        if h.is_location_specific and loc_id:
            if not h.location_ids or loc_id not in h.location_ids:
                keep = False
        elif h.is_location_specific and not loc_id:
            # If searching globally, maybe show all? Or maybe location specific ones are only for their locations.
            # Usually we show all holidays in a global calendar or just org-wide ones.
            pass
        
        if keep and h.is_department_specific and dept_id:
            if not h.department_ids or dept_id not in h.department_ids:
                keep = False
        
        if keep:
            filtered_holidays.append(h)

    # 7. Transform to Calendar Events
    leave_events = []
    for app in applications:
        leave_events.append(LeaveCalendarEvent(
            uuid=app.uuid,
            employee_name=f"{app.employee.first_name} {app.employee.last_name}",
            employee_uuid=app.employee.uuid,
            leave_type_name=app.leave_type.leave_name,
            from_date=app.from_date,
            to_date=app.to_date,
            status=app.status,
            is_half_day=app.is_half_day,
            total_days=app.total_days
        ))

    holiday_events = []
    for h in filtered_holidays:
        holiday_events.append(HolidayCalendarEvent(
            uuid=h.uuid,
            holiday_name=h.holiday_name,
            holiday_date=h.holiday_date,
            holiday_type=h.holiday_type,
            description=h.description,
            is_optional=h.is_optional,
            is_restricted=h.is_restricted
        ))

    return LeaveCalendarResponse(
        success=True,
        message="Leave calendar retrieved successfully",
        data=LeaveCalendarData(
            leaves=leave_events,
            holidays=holiday_events
        )
    )

@router.get("/team", response_model=LeaveCalendarResponse)
def get_team_leave_calendar(
    manager_uuid: uuid.UUID = Query(..., description="UUID of the manager"),
    from_date: Optional[date] = Query(None, description="Start date of the range"),
    to_date: Optional[date] = Query(None, description="End date of the range"),
    db: Session = Depends(deps.get_db),
    current_org: Organization = Depends(deps.get_current_org)
):
    """
    Get leave calendar for all members reporting to a specific manager.
    """
    # 1. Resolve manager
    manager = db.query(Employee).filter(
        Employee.uuid == manager_uuid, 
        Employee.organization_id == current_org.id
    ).first()
    
    if not manager:
        return JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND,
            content={"success": False, "message": "Manager not found", "data": []}
        )

    # 2. Get team members
    team_member_ids = [r[0] for r in db.query(Employee.id).filter(
        Employee.reporting_manager_id == manager.id,
        Employee.is_active == True
    ).all()]
    
    if not team_member_ids:
        return LeaveCalendarResponse(
            success=True,
            message="No team members found for this manager",
            data=LeaveCalendarData(leaves=[], holidays=[])
        )

    # 3. Base Query
    query = db.query(LeaveApplication).filter(
        LeaveApplication.employee_id.in_(team_member_ids),
        LeaveApplication.organization_id == current_org.id,
        LeaveApplication.status.in_([LeaveStatus.PENDING, LeaveStatus.APPROVED])
    )

    # 3.5 Date Range Filter for Leaves
    if from_date and to_date:
        query = query.filter(
            or_(
                and_(LeaveApplication.from_date <= from_date, LeaveApplication.to_date >= from_date),
                and_(LeaveApplication.from_date <= to_date, LeaveApplication.to_date >= to_date),
                and_(LeaveApplication.from_date >= from_date, LeaveApplication.to_date <= to_date)
            )
        )
    elif from_date:
        query = query.filter(LeaveApplication.to_date >= from_date)
    elif to_date:
        query = query.filter(LeaveApplication.from_date <= to_date)

    # 4. Holiday Query
    holiday_query = db.query(Holiday).filter(
        Holiday.organization_id == current_org.id,
        Holiday.is_active == True,
        Holiday.is_deleted == False
    )

    if from_date and to_date:
        holiday_query = holiday_query.filter(
            Holiday.holiday_date >= from_date,
            Holiday.holiday_date <= to_date
        )
    elif from_date:
        holiday_query = holiday_query.filter(Holiday.holiday_date >= from_date)
    elif to_date:
        holiday_query = holiday_query.filter(Holiday.holiday_date <= to_date)

    # 5. Fetch Results
    applications = query.options(
        joinedload(LeaveApplication.employee),
        joinedload(LeaveApplication.leave_type)
    ).all()

    holidays = holiday_query.all()

    # 6. Transform to Calendar Events
    leave_events = []
    for app in applications:
        leave_events.append(LeaveCalendarEvent(
            uuid=app.uuid,
            employee_name=f"{app.employee.first_name} {app.employee.last_name}",
            employee_uuid=app.employee.uuid,
            leave_type_name=app.leave_type.leave_name,
            from_date=app.from_date,
            to_date=app.to_date,
            status=app.status,
            is_half_day=app.is_half_day,
            total_days=app.total_days
        ))

    holiday_events = []
    for h in holidays:
        holiday_events.append(HolidayCalendarEvent(
            uuid=h.uuid,
            holiday_name=h.holiday_name,
            holiday_date=h.holiday_date,
            holiday_type=h.holiday_type,
            description=h.description,
            is_optional=h.is_optional,
            is_restricted=h.is_restricted
        ))

    return LeaveCalendarResponse(
        success=True,
        message="Team leave calendar retrieved successfully",
        data=LeaveCalendarData(
            leaves=leave_events,
            holidays=holiday_events
        )
    )
