import uuid
from typing import List, Optional
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
from app.schemas.attendance import TimesheetListResponse, TimesheetResponse, TimesheetCreate, TimesheetUpdate, TimesheetApproval, TimesheetRejection, TimesheetEntryCreate, TimesheetEntryResponse

router = APIRouter()

@router.get("/", response_model=TimesheetListResponse)
def list_timesheets(
    db: Session = Depends(deps.get_db),
    current_org: Organization = Depends(deps.get_current_org),
    page: Optional[int] = Query(None, ge=1, description="Page number"),
    limit: int = Query(10, ge=1, description="Items per page"),
    employee_uuid: Optional[uuid.UUID] = Query(None, description="Filter by Employee UUID"),
    status: Optional[TimesheetStatus] = Query(None, description="Filter by Status"),
    period_start: Optional[date] = Query(None, description="Filter from period start date"),
    period_end: Optional[date] = Query(None, description="Filter to period end date")
):
    """
    List timesheets with filtering and pagination.
    """
    query = db.query(Timesheet).filter(
        Timesheet.organization_id == current_org.id,
        Timesheet.is_deleted == False
    )
    
    # 1. Joins for filtering if Employee UUID provided
    if employee_uuid:
        employee = db.query(Employee).filter(
            Employee.uuid == employee_uuid,
            Employee.organization_id == current_org.id
        ).first()
        if not employee:
            return TimesheetListResponse(
                success=True,
                message="Employee not found",
                data=[],
                pagination={"total_records": 0, "current_page": 1, "total_pages": 0, "page_size": limit}
            )
        query = query.filter(Timesheet.employee_id == employee.id)
        
    # 2. Other filters
    if status:
        query = query.filter(Timesheet.status == status)
    if period_start:
        query = query.filter(Timesheet.period_start_date >= period_start)
    if period_end:
        query = query.filter(Timesheet.period_end_date <= period_end)
        
    # 3. Optimization: Early loading
    query = query.options(
        joinedload(Timesheet.employee),
        joinedload(Timesheet.approver)
    ).order_by(Timesheet.period_start_date.desc())
    
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
            "page_size": total_records if total_records > 0 else 0
        }
        
    return TimesheetListResponse(
        success=True,
        message="Timesheets retrieved successfully",
        data=records,
        pagination=pagination_data
    )

@router.post("/", response_model=TimesheetResponse)
def create_timesheet(
    *,
    db: Session = Depends(deps.get_db),
    current_org: Organization = Depends(deps.get_current_org),
    timesheet_in: TimesheetCreate
):
    """
    Create a new timesheet with entries.
    """
    # 1. Validate employee
    employee = db.query(Employee).filter(
        Employee.uuid == timesheet_in.employee_uuid,
        Employee.organization_id == current_org.id
    ).first()
    
    if not employee:
        return JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND,
            content={"success": False, "message": "Employee not found", "data": None}
        )

    # 2. Check for existing timesheet for this period
    existing = db.query(Timesheet).filter(
        Timesheet.employee_id == employee.id,
        Timesheet.period_start_date == timesheet_in.period_start_date,
        Timesheet.period_end_date == timesheet_in.period_end_date,
        Timesheet.organization_id == current_org.id,
        Timesheet.is_deleted == False
    ).first()
    
    if existing:
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={"success": False, "message": "Timesheet for this period already exists", "data": None}
        )

    # 3. Calculate Totals
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

    # 4. Create Timesheet
    # Default approver is reporting manager
    approver_id = employee.reporting_manager_id
    
    timesheet = Timesheet(
        organization_id=current_org.id,
        employee_id=employee.id,
        period_start_date=timesheet_in.period_start_date,
        period_end_date=timesheet_in.period_end_date,
        period_type=timesheet_in.period_type,
        total_hours=total_hours,
        billable_hours=billable_hours,
        non_billable_hours=non_billable_hours,
        status=TimesheetStatus.DRAFT,
        notes=timesheet_in.notes,
        approver_id=approver_id
    )
    
    db.add(timesheet)
    db.flush() # Get timesheet ID

    # 5. Create Entries
    for entry_data in timesheet_in.entries:
        entry = TimesheetEntry(
            timesheet_id=timesheet.id,
            employee_id=employee.id,
            entry_date=entry_data.entry_date,
            project_id=entry_data.project_id,
            project_name=entry_data.project_name,
            task_id=entry_data.task_id,
            task_name=entry_data.task_name,
            activity_description=entry_data.activity_description,
            hours_worked=Decimal(str(entry_data.hours_worked)),
            is_billable=entry_data.is_billable,
            client_id=entry_data.client_id,
            client_name=entry_data.client_name,
            notes=entry_data.notes
        )
        db.add(entry)
    
    db.commit()
    db.refresh(timesheet)
    
    return TimesheetResponse(
        success=True,
        message="Timesheet created successfully",
        data=timesheet
    )

@router.get("/{timesheet_uuid}", response_model=TimesheetResponse)
def get_timesheet(
    timesheet_uuid: uuid.UUID,
    db: Session = Depends(deps.get_db),
    current_org: Organization = Depends(deps.get_current_org)
):
    """
    Get detailed information for a specific timesheet, including all entries.
    """
    timesheet = db.query(Timesheet).filter(
        Timesheet.uuid == timesheet_uuid,
        Timesheet.organization_id == current_org.id,
        Timesheet.is_deleted == False
    ).options(
        joinedload(Timesheet.employee),
        joinedload(Timesheet.approver),
        joinedload(Timesheet.entries)
    ).first()
    
    if timesheet:
        # Filter soft-deleted entries for response
        timesheet.entries = [e for e in timesheet.entries if not e.is_deleted]
    
    if not timesheet:
        return JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND,
            content={"success": False, "message": "Timesheet not found", "data": None}
        )
        
    return TimesheetResponse(
        success=True,
        message="Timesheet retrieved successfully",
        data=timesheet
    )

@router.put("/{timesheet_uuid}", response_model=TimesheetResponse)
def update_timesheet(
    timesheet_uuid: uuid.UUID,
    timesheet_in: TimesheetUpdate,
    db: Session = Depends(deps.get_db),
    current_org: Organization = Depends(deps.get_current_org)
):
    """
    Update an existing timesheet. Only allowed if status is 'DRAFT'.
    """
    # 1. Fetch Timesheet
    timesheet = db.query(Timesheet).filter(
        Timesheet.uuid == timesheet_uuid,
        Timesheet.organization_id == current_org.id,
        Timesheet.is_deleted == False
    ).first()
    
    if not timesheet:
        return JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND,
            content={"success": False, "message": "Timesheet not found", "data": None}
        )
        
    # 2. Check Status
    if timesheet.status != TimesheetStatus.DRAFT:
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={"success": False, "message": f"Cannot edit timesheet with status '{timesheet.status}'. Only DRAFT can be edited.", "data": None}
        )

    # 3. Update Headers
    if timesheet_in.notes is not None:
        timesheet.notes = timesheet_in.notes
        
    # 4. Calculate Totals
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
            
    timesheet.total_hours = total_hours
    timesheet.billable_hours = billable_hours
    timesheet.non_billable_hours = non_billable_hours

    # 5. Replace Entries
    # Soft delete existing entries
    db.query(TimesheetEntry).filter(TimesheetEntry.timesheet_id == timesheet.id).update({TimesheetEntry.is_deleted: True})
    
    # Create new entries
    for entry_data in timesheet_in.entries:
        entry = TimesheetEntry(
            timesheet_id=timesheet.id,
            employee_id=timesheet.employee_id, # Inherit from timesheet
            entry_date=entry_data.entry_date,
            project_id=entry_data.project_id,
            project_name=entry_data.project_name,
            task_id=entry_data.task_id,
            task_name=entry_data.task_name,
            activity_description=entry_data.activity_description,
            hours_worked=Decimal(str(entry_data.hours_worked)),
            is_billable=entry_data.is_billable,
            client_id=entry_data.client_id,
            client_name=entry_data.client_name,
            notes=entry_data.notes
        )
        db.add(entry)
        
    db.commit()
    db.refresh(timesheet)
    
    return TimesheetResponse(
        success=True,
        message="Timesheet updated successfully",
        data=timesheet
    )

@router.post("/{timesheet_uuid}/submit", response_model=TimesheetResponse)
def submit_timesheet(
    timesheet_uuid: uuid.UUID,
    db: Session = Depends(deps.get_db),
    current_org: Organization = Depends(deps.get_current_org)
):
    """
    Submit a timesheet for approval.
    """
    # 1. Fetch Timesheet
    timesheet = db.query(Timesheet).filter(
        Timesheet.uuid == timesheet_uuid,
        Timesheet.organization_id == current_org.id,
        Timesheet.is_deleted == False
    ).first()
    
    if not timesheet:
        return JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND,
            content={"success": False, "message": "Timesheet not found", "data": None}
        )
        
    # 2. Check Status
    if timesheet.status != TimesheetStatus.DRAFT:
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={"success": False, "message": f"Timesheet is already {timesheet.status}", "data": None}
        )

    # 3. Update Status
    timesheet.status = TimesheetStatus.SUBMITTED
    timesheet.submitted_at = datetime.utcnow()
    
    db.commit()
    db.refresh(timesheet)
    
    return TimesheetResponse(
        success=True,
        message="Timesheet submitted successfully",
        data=timesheet
    )

@router.patch("/{timesheet_uuid}/approve", response_model=TimesheetResponse)
def approve_timesheet(
    timesheet_uuid: uuid.UUID,
    approval_in: TimesheetApproval,
    db: Session = Depends(deps.get_db),
    current_org: Organization = Depends(deps.get_current_org)
):
    """
    Approve a submitted timesheet.
    """
    # 1. Fetch Timesheet
    timesheet = db.query(Timesheet).filter(
        Timesheet.uuid == timesheet_uuid,
        Timesheet.organization_id == current_org.id,
        Timesheet.is_deleted == False
    ).first()
    
    if not timesheet:
        return JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND,
            content={"success": False, "message": "Timesheet not found", "data": None}
        )
        
    # 2. Check Status
    if timesheet.status != TimesheetStatus.SUBMITTED:
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={"success": False, "message": f"Timesheet is currently in '{timesheet.status}' status. Only SUBMITTED timesheets can be approved.", "data": None}
        )

    # 3. Update Status
    timesheet.status = TimesheetStatus.APPROVED
    timesheet.approved_at = datetime.utcnow()
    timesheet.approver_comments = approval_in.comments
    
    # Note: Logic to update payroll or trigger payment can be added here
    
    db.commit()
    db.refresh(timesheet)
    
    return TimesheetResponse(
        success=True,
        message="Timesheet approved successfully",
        data=timesheet
    )

@router.patch("/{timesheet_uuid}/reject", response_model=TimesheetResponse)
def reject_timesheet(
    timesheet_uuid: uuid.UUID,
    rejection_in: TimesheetRejection,
    db: Session = Depends(deps.get_db),
    current_org: Organization = Depends(deps.get_current_org)
):
    """
    Reject a submitted timesheet.
    """
    # 1. Fetch Timesheet
    timesheet = db.query(Timesheet).filter(
        Timesheet.uuid == timesheet_uuid,
        Timesheet.organization_id == current_org.id,
        Timesheet.is_deleted == False
    ).first()
    
    if not timesheet:
        return JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND,
            content={"success": False, "message": "Timesheet not found", "data": None}
        )
        
    # 2. Check Status
    if timesheet.status != TimesheetStatus.SUBMITTED:
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={"success": False, "message": f"Timesheet is currently in '{timesheet.status}' status. Only SUBMITTED timesheets can be rejected.", "data": None}
        )

    # 3. Update Status
    timesheet.status = TimesheetStatus.REJECTED
    timesheet.rejected_at = datetime.utcnow()
    timesheet.rejection_reason = rejection_in.rejection_reason
    
    db.commit()
    db.refresh(timesheet)
    
    return TimesheetResponse(
        success=True,
        message="Timesheet rejected successfully",
        data=timesheet
    )

@router.post("/{timesheet_uuid}/entries", response_model=TimesheetEntryResponse)
def add_timesheet_entry(
    timesheet_uuid: uuid.UUID,
    entry_in: TimesheetEntryCreate,
    db: Session = Depends(deps.get_db),
    current_org: Organization = Depends(deps.get_current_org)
):
    """
    Add a single entry to an existing timesheet. Only allowed if status is 'DRAFT'.
    """
    # 1. Fetch Timesheet
    timesheet = db.query(Timesheet).filter(
        Timesheet.uuid == timesheet_uuid,
        Timesheet.organization_id == current_org.id,
        Timesheet.is_deleted == False
    ).first()
    
    if not timesheet:
        return JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND,
            content={"success": False, "message": "Timesheet not found", "data": None}
        )
        
    # 2. Check Status
    if timesheet.status != TimesheetStatus.DRAFT:
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={"success": False, "message": f"Cannot add entry to timesheet with status '{timesheet.status}'. Only DRAFT can be edited.", "data": None}
        )

    # 3. Create Entry
    entry = TimesheetEntry(
        timesheet_id=timesheet.id,
        employee_id=timesheet.employee_id,
        entry_date=entry_in.entry_date,
        project_id=entry_in.project_id,
        project_name=entry_in.project_name,
        task_id=entry_in.task_id,
        task_name=entry_in.task_name,
        activity_description=entry_in.activity_description,
        hours_worked=Decimal(str(entry_in.hours_worked)),
        is_billable=entry_in.is_billable,
        client_id=entry_in.client_id,
        client_name=entry_in.client_name,
        notes=entry_in.notes
    )
    db.add(entry)
    
    # 4. Update Timesheet Totals
    hours = Decimal(str(entry_in.hours_worked))
    timesheet.total_hours += hours
    if entry_in.is_billable:
        timesheet.billable_hours += hours
    else:
        timesheet.non_billable_hours += hours
        
    db.commit()
    db.refresh(entry)
    
    return TimesheetEntryResponse(
        success=True,
        message="Timesheet entry added successfully",
        data=entry
    )
