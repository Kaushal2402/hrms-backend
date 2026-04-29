import uuid
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session, joinedload
from decimal import Decimal

from app.api import deps
from app.models.attendance import Timesheet, TimesheetEntry, TimesheetStatus
from app.models.organization import Organization
from app.schemas.attendance import TimesheetEntryUpdate, TimesheetEntryResponse

router = APIRouter()

@router.put("/{entry_uuid}", response_model=TimesheetEntryResponse)
def update_timesheet_entry(
    entry_uuid: uuid.UUID,
    entry_in: TimesheetEntryUpdate,
    db: Session = Depends(deps.get_db),
    current_org: Organization = Depends(deps.get_current_org)
):
    """
    Update a specific timesheet entry. Only allowed if the parent timesheet is in DRAFT status.
    """
    # 1. Fetch Entry
    entry = db.query(TimesheetEntry).filter(
        TimesheetEntry.uuid == entry_uuid,
        TimesheetEntry.is_deleted == False
    ).first()
    
    # Verify organization through join or manual check (Entry doesn't have org_id directly? 
    # Let's check model. TimesheetEntry has timesheet_id, employee_id. Timesheet has organization_id.
    # Joining is safer.)
    if not entry:
         return JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND,
            content={"success": False, "message": "Timesheet entry not found", "data": None}
        )
        
    timesheet = db.query(Timesheet).filter(
        Timesheet.id == entry.timesheet_id,
        Timesheet.organization_id == current_org.id,
        Timesheet.is_deleted == False
    ).first()
    
    if not timesheet:
        # If entry exists but timesheet doesn't belong to org (or doesn't exist), return 404
        return JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND,
            content={"success": False, "message": "Timesheet entry not found", "data": None}
        )

    # 2. Check Status
    if timesheet.status != TimesheetStatus.DRAFT:
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={"success": False, "message": f"Cannot edit entry because timesheet is in '{timesheet.status}' status.", "data": None}
        )

    # 3. Capture Old Values for Recalculation
    old_hours = Decimal(str(entry.hours_worked))
    old_billable = entry.is_billable
    
    # 4. Update Fields
    if entry_in.entry_date is not None:
        entry.entry_date = entry_in.entry_date
    if entry_in.project_id is not None:
        entry.project_id = entry_in.project_id
    if entry_in.project_name is not None:
        entry.project_name = entry_in.project_name
    if entry_in.task_id is not None:
        entry.task_id = entry_in.task_id
    if entry_in.task_name is not None:
        entry.task_name = entry_in.task_name
    if entry_in.activity_description is not None:
        entry.activity_description = entry_in.activity_description
    if entry_in.hours_worked is not None:
        entry.hours_worked = entry_in.hours_worked
    if entry_in.is_billable is not None:
        entry.is_billable = entry_in.is_billable
    if entry_in.client_id is not None:
        entry.client_id = entry_in.client_id
    if entry_in.client_name is not None:
        entry.client_name = entry_in.client_name
    if entry_in.notes is not None:
        entry.notes = entry_in.notes
        
    # 5. Recalculate Totals
    # New values
    new_hours = Decimal(str(entry.hours_worked))
    new_billable = entry.is_billable
    
    # Adjust Total Hours
    timesheet.total_hours = timesheet.total_hours - old_hours + new_hours
    
    # Adjust Billable/Non-Billable
    # Logic: Remove old contribution, Add new contribution
    
    if old_billable:
        timesheet.billable_hours -= old_hours
    else:
        timesheet.non_billable_hours -= old_hours
        
    if new_billable:
        timesheet.billable_hours += new_hours
    else:
        timesheet.non_billable_hours += new_hours

    db.commit()
    db.refresh(entry)
    
    return TimesheetEntryResponse(
        success=True,
        message="Timesheet entry updated successfully",
        data=entry
    )

@router.delete("/{entry_uuid}")
def delete_timesheet_entry(
    entry_uuid: uuid.UUID,
    db: Session = Depends(deps.get_db),
    current_org: Organization = Depends(deps.get_current_org)
):
    """
    Delete a timesheet entry. Only allowed if parent timesheet is in DRAFT status.
    """
    # 1. Fetch Entry
    entry = db.query(TimesheetEntry).filter(
        TimesheetEntry.uuid == entry_uuid,
        TimesheetEntry.is_deleted == False
    ).first()
    
    if not entry:
        return JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND,
            content={"success": False, "message": "Timesheet entry not found", "data": None}
        )
        
    timesheet = db.query(Timesheet).filter(
        Timesheet.id == entry.timesheet_id,
        Timesheet.organization_id == current_org.id,
        Timesheet.is_deleted == False
    ).first()
    
    if not timesheet:
        return JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND,
            content={"success": False, "message": "Timesheet entry not found", "data": None}
        )

    # 2. Check Status
    if timesheet.status != TimesheetStatus.DRAFT:
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={"success": False, "message": f"Cannot delete entry because timesheet is in '{timesheet.status}' status.", "data": None}
        )
        
    # 3. Adjust Totals Before Deletion
    hours = Decimal(str(entry.hours_worked))
    timesheet.total_hours -= hours
    
    if entry.is_billable:
        timesheet.billable_hours -= hours
    else:
        timesheet.non_billable_hours -= hours
        
    # 4. Soft Delete
    entry.is_deleted = True
    db.commit()
    
    return {"success": True, "message": "Timesheet entry deleted successfully"}
