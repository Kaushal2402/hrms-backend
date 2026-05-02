import uuid
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks, status
from sqlalchemy.orm import Session
from app.api import deps
from app.models.organization import Organization, Industry
from app.models.industry_templates import (
    IndustryDepartmentTemplate, IndustryJobTitleTemplate, IndustryRoleTemplate,
    IndustryShiftTemplate, IndustryAttendancePolicyTemplate, MasterCountryHoliday,
    IndustryLeaveTypeTemplate, IndustryLeavePolicyTemplate,
    QuickSetupJob, QuickSetupStatus
)
from app.schemas.quick_setup import (
    IndustrySuggestionsResponse, QuickSetupRequest, QuickSetupJobResponse
)
from app.utils.onboarding import get_onboarding_progress
from app.services.quick_setup import run_quick_setup_background
from app.utils.holidays import fetch_holidays_from_api

router = APIRouter()

@router.get("/suggestions", response_model=IndustrySuggestionsResponse)
def get_quick_setup_suggestions(
    db: Session = Depends(deps.get_db),
    current_org: Organization = Depends(deps.get_current_org)
):
    """
    Get suggested configurations based on the organization's industry and profile.
    """
    # Find Industry
    industry = db.query(Industry).filter(Industry.name == current_org.industry).first()
    if not industry:
        # Try to find by industry_id if it's set
        if current_org.industry_id:
            industry = db.query(Industry).get(current_org.industry_id)
    
    if not industry:
        raise HTTPException(status_code=404, detail="Industry not found for this organization. Please update your profile.")

    # Fetch Templates
    depts = db.query(IndustryDepartmentTemplate).filter(IndustryDepartmentTemplate.industry_id == industry.id).all()
    titles = db.query(IndustryJobTitleTemplate).filter(IndustryJobTitleTemplate.industry_id == industry.id).all()
    roles = db.query(IndustryRoleTemplate).filter(IndustryRoleTemplate.industry_id == industry.id).all()
    shifts = db.query(IndustryShiftTemplate).filter(IndustryShiftTemplate.industry_id == industry.id).all()
    policies = db.query(IndustryAttendancePolicyTemplate).filter(IndustryAttendancePolicyTemplate.industry_id == industry.id).all()
    leave_types = db.query(IndustryLeaveTypeTemplate).filter(IndustryLeaveTypeTemplate.industry_id == industry.id).all()
    leave_policies = db.query(IndustryLeavePolicyTemplate).filter(IndustryLeavePolicyTemplate.industry_id == industry.id).all()
    
    # Fetch Contextual Defaults (Real Holidays from API)
    api_holidays = fetch_holidays_from_api(current_org.country or "India")
    
    return {
        "success": True,
        "message": "Suggestions retrieved successfully",
        "data": {
            "industry_name": industry.name,
            "departments": depts,
            "job_titles": titles,
            "roles": roles,
            "shifts": shifts,
            "attendance_policies": policies,
            "leave_types": leave_types,
            "leave_policies": leave_policies,
            "holidays": api_holidays,
            "location_suggestion": f"Headquarters in {current_org.city or 'Main Office'}"
        }
    }

@router.post("/execute", response_model=QuickSetupJobResponse)
def execute_quick_setup(
    *,
    db: Session = Depends(deps.get_db),
    current_org: Organization = Depends(deps.get_current_org),
    setup_in: QuickSetupRequest,
    background_tasks: BackgroundTasks
):
    """
    Submit selected configurations for background execution.
    """
    # Create Job record
    job = QuickSetupJob(
        organization_id=current_org.id,
        selections=setup_in.model_dump(),
        status=QuickSetupStatus.PENDING
    )
    db.add(job)
    db.commit()
    db.refresh(job)

    # Trigger Background Task
    background_tasks.add_task(run_quick_setup_background, db, job.id)

    return {
        "success": True,
        "message": "Quick setup has started in the background. You can track progress here.",
        "job_uuid": job.uuid,
        "status": job.status
    }

@router.get("/status", response_model=QuickSetupJobResponse)
def get_quick_setup_status(
    db: Session = Depends(deps.get_db),
    current_org: Organization = Depends(deps.get_current_org)
):
    """
    Check the status of the latest quick setup job for the organization.
    """
    job = db.query(QuickSetupJob).filter(
        QuickSetupJob.organization_id == current_org.id
    ).order_by(QuickSetupJob.created_at.desc()).first()
    
    if not job:
        raise HTTPException(status_code=404, detail="No quick setup jobs found for this organization.")
    
    return {
        "success": True,
        "message": f"Latest job status: {job.status}",
        "job_uuid": job.uuid,
        "status": job.status,
        "progress_percentage": job.progress_percentage or 0,
        "logs": job.logs or []
    }
