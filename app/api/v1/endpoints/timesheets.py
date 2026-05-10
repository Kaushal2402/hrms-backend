import uuid
from typing import List, Optional, Union
from fastapi import APIRouter, Depends, HTTPException, status, Query
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import or_, func
from datetime import datetime, date, timedelta

from decimal import Decimal
from app.api import deps
from app.models.attendance import Timesheet, TimesheetEntry, TimesheetStatus
from app.models.employee import Employee
from app.models.organization import Organization
from app.models.projects import Project, ProjectTask, ProjectClient
from app.schemas.attendance import TimesheetListResponse, TimesheetResponse, TimesheetCreate, TimesheetUpdate, TimesheetApproval, TimesheetRejection, TimesheetEntryCreate, TimesheetEntryResponse

router = APIRouter()

def _org_id(user):
    return user.id if isinstance(user, Organization) else user.organization_id

def _require_timesheet_access(db: Session, user: Union[Organization, Employee], code: str, timesheet: Optional[Timesheet] = None, action_type: str = "read"):
    if isinstance(user, Organization):
        return True
    
    # 1. Global RBAC Check
    if deps.has_permission(db, user, code):
        return True
        
    # 2. Self-Service Logic (Ownership check)
    if timesheet:
        if timesheet.employee_id == user.id:
            if action_type == "delete":
                if timesheet.status == TimesheetStatus.DRAFT:
                    return True
                raise HTTPException(status_code=403, detail="Employees can only delete their own DRAFT timesheets")
            return True # view, update, submit allowed for owner
            
    # 3. Special case for Create (Permission 95)
    if code == "95" and action_type == "create":
        return True

    # 4. Special case for List (Permission 94)
    if code == "94" and action_type == "list":
        return True

    raise HTTPException(status_code=403, detail=f"No permission to {action_type} timesheets (code: {code})")

@router.get("/", response_model=TimesheetListResponse)
def list_timesheets(
    db: Session = Depends(deps.get_db),
    current_user: Union[Organization, Employee] = Depends(deps.get_current_user),
    page: Optional[int] = Query(None, ge=1, description="Page number"),
    limit: int = Query(10, ge=1, description="Items per page"),
    employee_uuid: Optional[uuid.UUID] = Query(None, description="Filter by Employee UUID"),
    status: Optional[TimesheetStatus] = Query(None, description="Filter by Status"),
    period_start: Optional[date] = Query(None, description="Filter from period start date"),
    period_end: Optional[date] = Query(None, description="Filter to period end date"),
    sort_by: Optional[str] = Query("period_start_date", description="Sort by field"),
    sort_order: Optional[str] = Query("desc", description="Sort order (asc/desc)")
):
    _require_timesheet_access(db, current_user, "94", action_type="list")
    org_id = _org_id(current_user)

    query = db.query(Timesheet).filter(
        Timesheet.organization_id == org_id,
        Timesheet.is_deleted == False
    )

    if isinstance(current_user, Employee) and not deps.has_permission(db, current_user, "94"):
        query = query.filter(Timesheet.employee_id == current_user.id)
    
    if employee_uuid:
        employee = db.query(Employee).filter(
            Employee.uuid == employee_uuid,
            Employee.organization_id == org_id
        ).first()
        if not employee:
            return TimesheetListResponse(
                success=True, message="Employee not found", data=[],
                pagination={"total_records": 0, "current_page": 1, "total_pages": 0, "page_size": limit}
            )
        query = query.filter(Timesheet.employee_id == employee.id)
        
    if status:
        query = query.filter(Timesheet.status == status)
    if period_start:
        query = query.filter(Timesheet.period_start_date >= period_start)
    if period_end:
        query = query.filter(Timesheet.period_start_date <= period_end)
        
    query = query.options(
        joinedload(Timesheet.employee),
        joinedload(Timesheet.approver),
        joinedload(Timesheet.entries).joinedload(TimesheetEntry.project).joinedload(Project.client),
        joinedload(Timesheet.entries).joinedload(TimesheetEntry.task)
    )

    # Dynamic Sorting
    sort_fields = {
        "period_start_date": Timesheet.period_start_date,
        "total_hours": Timesheet.total_hours,
        "status": Timesheet.status,
        "updated_at": Timesheet.updated_at
    }
    
    order_field = sort_fields.get(sort_by, Timesheet.period_start_date)
    if sort_order == "desc":
        query = query.order_by(order_field.desc())
    else:
        query = query.order_by(order_field.asc())
    
    total_records = query.count()
    if page is not None:
        total_pages = (total_records + limit - 1) // limit
        skip = (page - 1) * limit
        records = query.offset(skip).limit(limit).all()
        pagination_data = {"total_records": total_records, "current_page": page, "total_pages": total_pages, "page_size": limit}
    else:
        records = query.all()
        pagination_data = {"total_records": total_records, "current_page": 1, "total_pages": 1, "page_size": total_records if total_records > 0 else 0}
        
    return TimesheetListResponse(success=True, message="Timesheets retrieved successfully", data=records, pagination=pagination_data)

@router.post("/", response_model=TimesheetResponse)
def create_timesheet(
    *,
    db: Session = Depends(deps.get_db),
    current_user: Union[Organization, Employee] = Depends(deps.get_current_user),
    timesheet_in: TimesheetCreate
):
    _require_timesheet_access(db, current_user, "95", action_type="create")
    org_id = _org_id(current_user)

    employee = db.query(Employee).filter(Employee.uuid == timesheet_in.employee_uuid, Employee.organization_id == org_id).first()
    if not employee:
        return JSONResponse(status_code=status.HTTP_404_NOT_FOUND, content={"success": False, "message": "Employee not found", "data": None})

    if isinstance(current_user, Employee) and not deps.has_permission(db, current_user, "95"):
        if employee.id != current_user.id:
            raise HTTPException(status_code=403, detail="You can only create timesheets for yourself")

    existing = db.query(Timesheet).filter(
        Timesheet.employee_id == employee.id,
        Timesheet.period_start_date == timesheet_in.period_start_date,
        Timesheet.period_end_date == timesheet_in.period_end_date,
        Timesheet.organization_id == org_id,
        Timesheet.is_deleted == False
    ).first()
    
    if existing:
        return JSONResponse(status_code=status.HTTP_400_BAD_REQUEST, content={"success": False, "message": "Timesheet for this period already exists", "data": None})

    total_hours = Decimal('0.00')
    billable_hours = Decimal('0.00')
    non_billable_hours = Decimal('0.00')
    
    for entry in timesheet_in.entries:
        hours = Decimal(str(entry.hours_worked))
        total_hours += hours
        if entry.is_billable:
            billable_hours += hours
        else:
            non_billable_hours += hours

    timesheet = Timesheet(
        organization_id=org_id, employee_id=employee.id,
        period_start_date=timesheet_in.period_start_date, period_end_date=timesheet_in.period_end_date,
        period_type=timesheet_in.period_type, total_hours=total_hours,
        billable_hours=billable_hours, non_billable_hours=non_billable_hours,
        status=TimesheetStatus.DRAFT, notes=timesheet_in.notes, approver_id=employee.reporting_manager_id
    )
    db.add(timesheet)
    db.flush()

    for entry_data in timesheet_in.entries:
        project = None
        task = None
        client = None
        if entry_data.project_uuid:
            project = db.query(Project).filter(Project.uuid == entry_data.project_uuid, Project.organization_id == org_id).first()
        if entry_data.task_uuid:
            task = db.query(ProjectTask).filter(ProjectTask.uuid == entry_data.task_uuid, ProjectTask.organization_id == org_id).first()
        if entry_data.client_uuid:
            client = db.query(ProjectClient).filter(ProjectClient.uuid == entry_data.client_uuid, ProjectClient.organization_id == org_id).first()
        elif project and project.client:
            client = project.client

        entry = TimesheetEntry(
            timesheet_id=timesheet.id, employee_id=employee.id, entry_date=entry_data.entry_date,
            project_id=project.id if project else None, project_name=project.project_name if project else None,
            task_id=task.id if task else None, task_name=task.task_name if task else None,
            activity_description=entry_data.activity_description, hours_worked=Decimal(str(entry_data.hours_worked)),
            is_billable=entry_data.is_billable, client_id=client.id if client else None,
            client_name=client.client_name if client else None, notes=entry_data.notes
        )
        db.add(entry)
    
    db.commit()
    db.refresh(timesheet)
    return TimesheetResponse(success=True, message="Timesheet created successfully", data=timesheet)

@router.get("/{timesheet_uuid}", response_model=TimesheetResponse)
def get_timesheet(timesheet_uuid: uuid.UUID, db: Session = Depends(deps.get_db), current_user: Union[Organization, Employee] = Depends(deps.get_current_user)):
    timesheet = db.query(Timesheet).filter(
        Timesheet.uuid == timesheet_uuid,
        Timesheet.organization_id == _org_id(current_user),
        Timesheet.is_deleted == False
    ).options(
        joinedload(Timesheet.employee),
        joinedload(Timesheet.approver),
        joinedload(Timesheet.entries).joinedload(TimesheetEntry.project).joinedload(Project.client),
        joinedload(Timesheet.entries).joinedload(TimesheetEntry.task)
    ).first()
    if not timesheet:
        return JSONResponse(status_code=status.HTTP_404_NOT_FOUND, content={"success": False, "message": "Timesheet not found", "data": None})
    _require_timesheet_access(db, current_user, "94", timesheet=timesheet, action_type="view")
    return TimesheetResponse(success=True, message="Timesheet retrieved successfully", data=timesheet)

@router.put("/{timesheet_uuid}", response_model=TimesheetResponse)
def update_timesheet(timesheet_uuid: uuid.UUID, timesheet_in: TimesheetUpdate, db: Session = Depends(deps.get_db), current_user: Union[Organization, Employee] = Depends(deps.get_current_user)):
    org_id = _org_id(current_user)
    timesheet = db.query(Timesheet).filter(Timesheet.uuid == timesheet_uuid, Timesheet.organization_id == org_id, Timesheet.is_deleted == False).first()
    if not timesheet:
        return JSONResponse(status_code=status.HTTP_404_NOT_FOUND, content={"success": False, "message": "Timesheet not found", "data": None})
    _require_timesheet_access(db, current_user, "96", timesheet=timesheet, action_type="update")
    if timesheet.status != TimesheetStatus.DRAFT:
        return JSONResponse(status_code=status.HTTP_400_BAD_REQUEST, content={"success": False, "message": f"Cannot edit timesheet with status '{timesheet.status}'. Only DRAFT can be edited.", "data": None})

    if timesheet_in.notes is not None:
        timesheet.notes = timesheet_in.notes
    total_hours = Decimal('0.00'); billable_hours = Decimal('0.00'); non_billable_hours = Decimal('0.00')
    for entry in timesheet_in.entries:
        hours = Decimal(str(entry.hours_worked)); total_hours += hours
        if entry.is_billable: billable_hours += hours
        else: non_billable_hours += hours
    timesheet.total_hours = total_hours; timesheet.billable_hours = billable_hours; timesheet.non_billable_hours = non_billable_hours

    # Hard delete old entries to prevent duplication in the relationship
    db.query(TimesheetEntry).filter(TimesheetEntry.timesheet_id == timesheet.id).delete(synchronize_session=False)
    for entry_data in timesheet_in.entries:
        project = None; task = None; client = None
        if entry_data.project_uuid: project = db.query(Project).filter(Project.uuid == entry_data.project_uuid, Project.organization_id == org_id).first()
        if entry_data.task_uuid: task = db.query(ProjectTask).filter(ProjectTask.uuid == entry_data.task_uuid, ProjectTask.organization_id == org_id).first()
        if entry_data.client_uuid: client = db.query(ProjectClient).filter(ProjectClient.uuid == entry_data.client_uuid, ProjectClient.organization_id == org_id).first()
        elif project and project.client: client = project.client
        entry = TimesheetEntry(
            timesheet_id=timesheet.id, employee_id=timesheet.employee_id, entry_date=entry_data.entry_date,
            project_id=project.id if project else None, project_name=project.project_name if project else None,
            task_id=task.id if task else None, task_name=task.task_name if task else None,
            activity_description=entry_data.activity_description, hours_worked=Decimal(str(entry_data.hours_worked)),
            is_billable=entry_data.is_billable, client_id=client.id if client else None,
            client_name=client.client_name if client else None, notes=entry_data.notes
        )
        db.add(entry)
    db.commit()
    db.refresh(timesheet)
    return TimesheetResponse(success=True, message="Timesheet updated successfully", data=timesheet)

@router.post("/{timesheet_uuid}/submit", response_model=TimesheetResponse)
def submit_timesheet(timesheet_uuid: uuid.UUID, db: Session = Depends(deps.get_db), current_user: Union[Organization, Employee] = Depends(deps.get_current_user)):
    org_id = _org_id(current_user)
    timesheet = db.query(Timesheet).filter(Timesheet.uuid == timesheet_uuid, Timesheet.organization_id == org_id, Timesheet.is_deleted == False).first()
    if not timesheet:
        return JSONResponse(status_code=status.HTTP_404_NOT_FOUND, content={"success": False, "message": "Timesheet not found", "data": None})
    _require_timesheet_access(db, current_user, "96", timesheet=timesheet, action_type="submit")
    if timesheet.status != TimesheetStatus.DRAFT:
        return JSONResponse(status_code=status.HTTP_400_BAD_REQUEST, content={"success": False, "message": f"Timesheet is already {timesheet.status}", "data": None})
    
    timesheet.status = TimesheetStatus.SUBMITTED
    timesheet.submitted_at = datetime.utcnow()
    if isinstance(current_user, Employee):
        timesheet.submitted_by = current_user.id
        
    db.commit()
    db.refresh(timesheet)
    return TimesheetResponse(success=True, message="Timesheet submitted successfully", data=timesheet)

@router.patch("/{timesheet_uuid}/approve", response_model=TimesheetResponse)
def approve_timesheet(timesheet_uuid: uuid.UUID, approval_in: TimesheetApproval, db: Session = Depends(deps.get_db), current_user: Union[Organization, Employee] = Depends(deps.get_current_user)):
    org_id = _org_id(current_user)
    timesheet = db.query(Timesheet).filter(Timesheet.uuid == timesheet_uuid, Timesheet.organization_id == org_id, Timesheet.is_deleted == False).first()
    if not timesheet:
        return JSONResponse(status_code=status.HTTP_404_NOT_FOUND, content={"success": False, "message": "Timesheet not found", "data": None})
    _require_timesheet_access(db, current_user, "96", action_type="approve")
    if timesheet.status != TimesheetStatus.SUBMITTED:
        return JSONResponse(status_code=status.HTTP_400_BAD_REQUEST, content={"success": False, "message": f"Timesheet is currently in '{timesheet.status}' status. Only SUBMITTED timesheets can be approved.", "data": None})
    timesheet.status = TimesheetStatus.APPROVED
    timesheet.approved_at = datetime.utcnow()
    timesheet.approver_comments = approval_in.comments
    db.commit()
    db.refresh(timesheet)
    return TimesheetResponse(success=True, message="Timesheet approved successfully", data=timesheet)

@router.patch("/{timesheet_uuid}/reject", response_model=TimesheetResponse)
def reject_timesheet(timesheet_uuid: uuid.UUID, rejection_in: TimesheetRejection, db: Session = Depends(deps.get_db), current_user: Union[Organization, Employee] = Depends(deps.get_current_user)):
    org_id = _org_id(current_user)
    timesheet = db.query(Timesheet).filter(Timesheet.uuid == timesheet_uuid, Timesheet.organization_id == org_id, Timesheet.is_deleted == False).first()
    if not timesheet:
        return JSONResponse(status_code=status.HTTP_404_NOT_FOUND, content={"success": False, "message": "Timesheet not found", "data": None})
    _require_timesheet_access(db, current_user, "96", action_type="reject")
    if timesheet.status != TimesheetStatus.SUBMITTED:
        return JSONResponse(status_code=status.HTTP_400_BAD_REQUEST, content={"success": False, "message": f"Timesheet is currently in '{timesheet.status}' status. Only SUBMITTED timesheets can be rejected.", "data": None})
    timesheet.status = TimesheetStatus.REJECTED
    timesheet.rejected_at = datetime.utcnow()
    timesheet.rejection_reason = rejection_in.rejection_reason
    db.commit()
    db.refresh(timesheet)
    return TimesheetResponse(success=True, message="Timesheet rejected successfully", data=timesheet)

@router.post("/{timesheet_uuid}/entries", response_model=TimesheetEntryResponse)
def add_timesheet_entry(timesheet_uuid: uuid.UUID, entry_in: TimesheetEntryCreate, db: Session = Depends(deps.get_db), current_user: Union[Organization, Employee] = Depends(deps.get_current_user)):
    org_id = _org_id(current_user)
    timesheet = db.query(Timesheet).filter(Timesheet.uuid == timesheet_uuid, Timesheet.organization_id == org_id, Timesheet.is_deleted == False).first()
    if not timesheet:
        return JSONResponse(status_code=status.HTTP_404_NOT_FOUND, content={"success": False, "message": "Timesheet not found", "data": None})
    _require_timesheet_access(db, current_user, "96", timesheet=timesheet, action_type="update")
    if timesheet.status != TimesheetStatus.DRAFT:
        return JSONResponse(status_code=status.HTTP_400_BAD_REQUEST, content={"success": False, "message": f"Cannot add entry to timesheet with status '{timesheet.status}'. Only DRAFT can be edited.", "data": None})
    project = None; task = None; client = None
    if entry_in.project_uuid: project = db.query(Project).filter(Project.uuid == entry_in.project_uuid, Project.organization_id == org_id).first()
    if entry_in.task_uuid: task = db.query(ProjectTask).filter(ProjectTask.uuid == entry_in.task_uuid, ProjectTask.organization_id == org_id).first()
    if entry_in.client_uuid: client = db.query(ProjectClient).filter(ProjectClient.uuid == entry_in.client_uuid, ProjectClient.organization_id == org_id).first()
    elif project and project.client: client = project.client
    entry = TimesheetEntry(
        timesheet_id=timesheet.id, employee_id=timesheet.employee_id, entry_date=entry_in.entry_date,
        project_id=project.id if project else None, project_name=project.project_name if project else None,
        task_id=task.id if task else None, task_name=task.task_name if task else None,
        activity_description=entry_in.activity_description, hours_worked=Decimal(str(entry_in.hours_worked)),
        is_billable=entry_in.is_billable, client_id=client.id if client else None,
        client_name=client.client_name if client else None, notes=entry_in.notes
    )
    db.add(entry)
    hours = Decimal(str(entry_in.hours_worked)); timesheet.total_hours += hours
    if entry_in.is_billable: timesheet.billable_hours += hours
    else: timesheet.non_billable_hours += hours
    db.commit(); db.refresh(entry)
    return TimesheetEntryResponse(success=True, message="Timesheet entry added successfully", data=entry)

@router.delete("/{timesheet_uuid}", response_model=TimesheetResponse)
def delete_timesheet(timesheet_uuid: uuid.UUID, db: Session = Depends(deps.get_db), current_user: Union[Organization, Employee] = Depends(deps.get_current_user)):
    org_id = _org_id(current_user)
    timesheet = db.query(Timesheet).filter(Timesheet.uuid == timesheet_uuid, Timesheet.organization_id == org_id, Timesheet.is_deleted == False).first()
    if not timesheet:
        return JSONResponse(status_code=status.HTTP_404_NOT_FOUND, content={"success": False, "message": "Timesheet not found", "data": None})
    _require_timesheet_access(db, current_user, "97", timesheet=timesheet, action_type="delete")
    timesheet.is_deleted = True
    db.commit()
    return TimesheetResponse(success=True, message="Timesheet deleted successfully", data=timesheet)
