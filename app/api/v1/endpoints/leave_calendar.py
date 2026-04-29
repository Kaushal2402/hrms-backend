import uuid
from datetime import date, datetime
from typing import List, Optional
from fastapi import APIRouter, Depends, Query, status
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import or_, and_

from app.api import deps
from app.models.attendance import LeaveApplication, LeaveType, LeaveStatus
from app.models.employee import Employee
from app.models.organization import Organization
from app.schemas.leave import LeaveCalendarResponse, LeaveCalendarEvent

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

    # 3. Department & Location Filters
    if department_uuid:
        # Resolve department if needed or just use join
        from app.models.employee import Department
        dept = db.query(Department).filter(Department.uuid == department_uuid).first()
        if dept:
            query = query.filter(Employee.department_id == dept.id)
        else:
            return LeaveCalendarResponse(success=True, message="Department not found", data=[])

    if location_uuid:
        from app.models.employee import Location
        loc = db.query(Location).filter(Location.uuid == location_uuid).first()
        if loc:
            query = query.filter(Employee.location_id == loc.id)
        else:
            return LeaveCalendarResponse(success=True, message="Location not found", data=[])

    # 4. Fetch Results
    applications = query.options(
        joinedload(LeaveApplication.employee),
        joinedload(LeaveApplication.leave_type)
    ).all()

    # 5. Transform to Calendar Events
    events = []
    for app in applications:
        events.append(LeaveCalendarEvent(
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

    return LeaveCalendarResponse(
        success=True,
        message="Leave calendar retrieved successfully",
        data=events
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
            data=[]
        )

    # 3. Base Query
    query = db.query(LeaveApplication).filter(
        LeaveApplication.employee_id.in_(team_member_ids),
        LeaveApplication.organization_id == current_org.id,
        LeaveApplication.status.in_([LeaveStatus.PENDING, LeaveStatus.APPROVED])
    )

    # 4. Date Range Filter
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

    # 5. Fetch Results
    applications = query.options(
        joinedload(LeaveApplication.employee),
        joinedload(LeaveApplication.leave_type)
    ).all()

    # 6. Transform to Calendar Events
    events = []
    for app in applications:
        events.append(LeaveCalendarEvent(
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

    return LeaveCalendarResponse(
        success=True,
        message="Team leave calendar retrieved successfully",
        data=events
    )
