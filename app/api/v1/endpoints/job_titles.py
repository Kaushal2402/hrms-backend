from typing import List, Optional, Union
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from app.api import deps
from app.models.employee import JobTitle
from app.schemas.job_title import (
    JobTitleSchema,
    JobTitleCreate,
    JobTitleUpdate,
    JobTitleResponse,
    JobTitleListResponse,
    JobTitleDetailResponse,
    JobTitleDetailSchema,
    JobTitleDeleteResponse
)
from app.models.organization import Organization
from app.models.employee import JobTitle, Employee
from datetime import datetime
import uuid

router = APIRouter()

@router.get("/", response_model=JobTitleListResponse)
def list_job_titles(
    db: Session = Depends(deps.get_db),
    current_org: Organization = Depends(deps.get_current_org),
    current_user: Union[Organization, Employee] = Depends(deps.get_current_user),
    is_active: Optional[bool] = Query(None, description="Filter by active status"),
    job_level: Optional[str] = Query(None, description="Filter by job level"),
    job_family: Optional[str] = Query(None, description="Filter by job family"),
    search: Optional[str] = Query(None, description="Search by title_name"),
    page: Optional[int] = Query(None, ge=1, description="Page number"),
    limit: int = Query(10, ge=1, description="Items per page"),
    sort_by: Optional[str] = Query("Recent", description="Sort by field: title_code, title_name, job_level, job_family, is_active, Recent, Oldest"),
    sort_order: str = Query("desc", description="Sort order: asc, desc"),
    authorized: bool = Depends(deps.check_permission("13"))
):
    """
    List all job titles for the authenticated organization.
    """
    query = db.query(JobTitle).filter(
        JobTitle.organization_id == current_org.id,
        JobTitle.is_deleted == False
    )
    
    if is_active is not None:
        query = query.filter(JobTitle.is_active == is_active)
        
    if job_level:
        query = query.filter(JobTitle.job_level == job_level)
        
    if job_family:
        query = query.filter(JobTitle.job_family == job_family)
        
    if search:
        search_term = f"%{search}%"
        query = query.filter(JobTitle.title_name.ilike(search_term))
        
    # Sorting logic
    sort_mapping = {
        "title_code": JobTitle.title_code,
        "title_name": JobTitle.title_name,
        "job_level": JobTitle.job_level,
        "job_family": JobTitle.job_family,
        "is_active": JobTitle.is_active,
        "Recent": JobTitle.id,
        "Oldest": JobTitle.id
    }
    
    # Default to ID if sort_by is not in mapping
    sort_field = sort_mapping.get(sort_by, JobTitle.id)
    
    # Handle Oldest specifically if no order is provided? 
    # But user said sort_order is provideed. 
    # If sort_by is Oldest and no order is provided, it should be asc.
    effective_order = sort_order.lower()
    if sort_by == "Oldest" and sort_order == "desc": # If user explicitly says Oldest + desc, well, obey it.
         effective_order = "desc"
    elif sort_by == "Oldest":
         effective_order = "asc"

    if effective_order == "asc":
        query = query.order_by(sort_field.asc())
    else:
        query = query.order_by(sort_field.desc())
        
    total_records = query.count()
    
    pagination_data = None
    if page is not None:
        total_pages = (total_records + limit - 1) // limit
        skip = (page - 1) * limit
        job_titles = query.offset(skip).limit(limit).all()
        pagination_data = {
            "total_records": total_records,
            "current_page": page,
            "total_pages": total_pages,
            "page_size": limit
        }
    else:
        job_titles = query.all()
        pagination_data = {
            "total_records": total_records,
            "current_page": 1,
            "total_pages": 1,
            "page_size": total_records if total_records > 0 else 0
        }
        
    if not job_titles:
        return JobTitleListResponse(
            success=False,
            message="No job titles found"
        )
        
    return JobTitleListResponse(
        success=True,
        message="Job titles retrieved successfully",
        data=job_titles,
        pagination=pagination_data
    )

@router.get("/lookup")
def lookup_job_titles(
    db: Session = Depends(deps.get_db),
    current_org: Organization = Depends(deps.get_current_org),
    search: Optional[str] = Query(None, description="Search by title_name or code"),
    limit: int = Query(100, ge=1, description="Limit lookup results")
):
    """
    Lite lookup endpoint for job titles (UUID, Title Name).
    Accessible to all authenticated users for filters/dropdowns.
    """
    query = db.query(JobTitle).filter(
        JobTitle.organization_id == current_org.id,
        JobTitle.is_active == True,
        JobTitle.is_deleted == False
    )
    
    if search:
        search_term = f"%{search}%"
        query = query.filter(
            (JobTitle.title_name.ilike(search_term)) |
            (JobTitle.title_code.ilike(search_term))
        )
        
    job_titles = query.order_by(JobTitle.title_name.asc()).limit(limit).all()
    
    return {
        "success": True,
        "data": [{"uuid": jt.uuid, "title_name": jt.title_name} for jt in job_titles]
    }

@router.post("/", response_model=JobTitleResponse)
def create_job_title(
    job_title_in: JobTitleCreate,
    db: Session = Depends(deps.get_db),
    current_org: Organization = Depends(deps.get_current_org),
    authorized: bool = Depends(deps.check_permission("14"))
):
    """
    Create a new job title.
    """
    # Check if job title with same code exists
    existing_title = db.query(JobTitle).filter(
        JobTitle.organization_id == current_org.id,
        JobTitle.title_code == job_title_in.title_code
    ).first()
    
    if existing_title:
        raise HTTPException(
            status_code=400,
            detail=f"Job title with code '{job_title_in.title_code}' already exists."
        )
        
    db_obj = JobTitle(
        **job_title_in.model_dump(),
        organization_id=current_org.id
    )
    db.add(db_obj)
    try:
        db.commit()
        db.refresh(db_obj)
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e))
        
    return JobTitleResponse(
        success=True,
        message="Job title created successfully",
        data=db_obj
    )

@router.get("/{title_uuid}", response_model=JobTitleDetailResponse)
def get_job_title(
    title_uuid: uuid.UUID,
    db: Session = Depends(deps.get_db),
    current_org: Organization = Depends(deps.get_current_org),
    authorized: bool = Depends(deps.check_permission("13"))
):
    """
    Get job title details with employee count.
    """
    job_title = db.query(JobTitle).filter(
        JobTitle.uuid == title_uuid,
        JobTitle.organization_id == current_org.id,
        JobTitle.is_deleted == False
    ).first()
    
    if not job_title:
        raise HTTPException(status_code=404, detail="Job title not found")
        
    # Count employees with this job title
    employee_count = db.query(Employee).filter(
        Employee.job_title_id == job_title.id,
        Employee.is_deleted == False
    ).count()
    
    title_data = JobTitleDetailSchema.model_validate(job_title)
    title_data.employee_count = employee_count
    
    return JobTitleDetailResponse(
        success=True,
        message="Job title retrieved successfully",
        data=title_data
    )

@router.put("/{title_uuid}", response_model=JobTitleResponse)
def update_job_title(
    title_uuid: uuid.UUID,
    job_title_in: JobTitleUpdate,
    db: Session = Depends(deps.get_db),
    current_org: Organization = Depends(deps.get_current_org),
    authorized: bool = Depends(deps.check_permission("15"))
):
    """
    Update a job title.
    """
    job_title = db.query(JobTitle).filter(
        JobTitle.uuid == title_uuid,
        JobTitle.organization_id == current_org.id,
        JobTitle.is_deleted == False
    ).first()
    
    if not job_title:
        raise HTTPException(status_code=404, detail="Job title not found")
        
    # Check duplicate code if being updated
    if job_title_in.title_code and job_title_in.title_code != job_title.title_code:
        existing_title = db.query(JobTitle).filter(
            JobTitle.organization_id == current_org.id,
            JobTitle.title_code == job_title_in.title_code
        ).first()
        if existing_title:
            raise HTTPException(
                status_code=400,
                detail=f"Job title with code '{job_title_in.title_code}' already exists."
            )
            
    update_data = job_title_in.model_dump(exclude_unset=True)
    
    for field, value in update_data.items():
        setattr(job_title, field, value)
        
    db.add(job_title)
    try:
        db.commit()
        db.refresh(job_title)
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e))
        
    return JobTitleResponse(
        success=True,
        message="Job title updated successfully",
        data=job_title
    )

@router.delete("/{title_uuid}", response_model=JobTitleDeleteResponse)
def delete_job_title(
    title_uuid: uuid.UUID,
    db: Session = Depends(deps.get_db),
    current_org: Organization = Depends(deps.get_current_org),
    authorized: bool = Depends(deps.check_permission("16"))
):
    """
    Delete a job title (soft delete).
    """
    job_title = db.query(JobTitle).filter(
        JobTitle.uuid == title_uuid,
        JobTitle.organization_id == current_org.id,
        JobTitle.is_deleted == False
    ).first()
    
    if not job_title:
        raise HTTPException(status_code=404, detail="Job title not found")
        
    # Check for dependencies
    # 1. Active Employees
    active_employees = db.query(Employee).filter(
        Employee.job_title_id == job_title.id,
        Employee.is_deleted == False
    ).count()
    
    if active_employees > 0:
        raise HTTPException(
            status_code=400,
            detail=f"Cannot delete job title. There are {active_employees} active employees assigned to it."
        )
        
    # Perform soft delete
    try:
        job_title.is_deleted = True
        job_title.deleted_at = datetime.utcnow()
        db.add(job_title)
        db.commit()
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e))
        
    return JobTitleDeleteResponse(
        success=True,
        message="Job title deleted successfully",
        data=None
    )
