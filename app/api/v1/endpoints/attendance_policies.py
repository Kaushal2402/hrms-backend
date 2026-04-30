import uuid
from typing import List, Optional
from datetime import datetime
from fastapi import APIRouter, Depends, Query, HTTPException, status
from sqlalchemy.orm import Session
from app.api import deps
from app.models.attendance import AttendancePolicy
from app.models.employee import Department, Location
from app.models.organization import Organization
from app.schemas.attendance import (
    AttendancePolicyListResponse, 
    AttendancePolicySchema, 
    AttendancePolicyCreate, 
    AttendancePolicyResponse,
    AttendancePolicyUpdate
)
from app.core.permissions import AttendancePolicyPermissions

router = APIRouter()

def populate_policy_uuids(policy: AttendancePolicy, db: Session) -> AttendancePolicySchema:
    """Helper to map department/location IDs to structured objects {uuid, name} for the response."""
    result = AttendancePolicySchema.model_validate(policy)
    
    if policy.department_ids:
        depts = db.query(Department.uuid, Department.department_name).filter(
            Department.id.in_(policy.department_ids)
        ).all()
        result.departments = [{"uuid": r[0], "name": r[1]} for r in depts]
        
    if policy.location_ids:
        locs = db.query(Location.uuid, Location.location_name).filter(
            Location.id.in_(policy.location_ids)
        ).all()
        result.locations = [{"uuid": r[0], "name": r[1]} for r in locs]
        
    return result

@router.post("/", response_model=AttendancePolicyResponse)
def create_attendance_policy(
    policy_in: AttendancePolicyCreate,
    db: Session = Depends(deps.get_db),
    current_org: Organization = Depends(deps.get_current_org),
    _: bool = Depends(deps.check_permission(AttendancePolicyPermissions.CREATE))
):
    """
    Create a new attendance policy for the organization.
    """
    # 1. Handle default policy logic
    if policy_in.is_default:
        # Unset existing default policy for this organization
        db.query(AttendancePolicy).filter(
            AttendancePolicy.organization_id == current_org.id,
            AttendancePolicy.is_default == True
        ).update({"is_default": False})

    # 2. Resolve UUIDs to IDs
    policy_data = policy_in.model_dump(exclude={'department_uuids', 'location_uuids', 'departments', 'locations'})
    
    department_uuids = getattr(policy_in, 'department_uuids', None)
    if department_uuids:
        dept_ids = db.query(Department.id).filter(
            Department.uuid.in_(department_uuids),
            Department.organization_id == current_org.id,
            Department.is_deleted == False
        ).all()
        policy_data['department_ids'] = [r[0] for r in dept_ids]

    location_uuids = getattr(policy_in, 'location_uuids', None)
    if location_uuids:
        loc_ids = db.query(Location.id).filter(
            Location.uuid.in_(location_uuids),
            Location.organization_id == current_org.id,
            Location.is_deleted == False
        ).all()
        policy_data['location_ids'] = [r[0] for r in loc_ids]

    # 3. Create record
    policy = AttendancePolicy(
        **policy_data,
        organization_id=current_org.id
    )

    db.add(policy)
    try:
        db.commit()
        db.refresh(policy)
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create attendance policy: {str(e)}"
        )

    return AttendancePolicyResponse(
        success=True,
        message="Attendance policy created successfully",
        data=populate_policy_uuids(policy, db)
    )

from sqlalchemy import or_

@router.get("/", response_model=AttendancePolicyListResponse)
def list_attendance_policies(
    db: Session = Depends(deps.get_db),
    current_org: Organization = Depends(deps.get_current_org),
    is_active: Optional[bool] = Query(None, description="Filter by active status"),
    search: Optional[str] = Query(None, description="Search by policy name or description"),
    sort_by: str = Query("policy_name", description="Sort by 'policy_name', 'created_at', or 'is_active'"),
    order: str = Query("asc", description="Sort order ('asc' or 'desc')"),
    page: int = Query(1, ge=1, description="Page number"),
    limit: int = Query(10, ge=1, description="Items per page"),
    _: bool = Depends(deps.check_permission(AttendancePolicyPermissions.READ))
):
    """
    List attendance policies with filtering, search, sorting and pagination.
    """
    query = db.query(AttendancePolicy).filter(
        AttendancePolicy.organization_id == current_org.id,
        AttendancePolicy.is_deleted == False
    )

    if is_active is not None:
        query = query.filter(AttendancePolicy.is_active == is_active)

    if search:
        search_term = f"%{search}%"
        query = query.filter(
            or_(
                AttendancePolicy.policy_name.ilike(search_term),
                AttendancePolicy.description.ilike(search_term)
            )
        )

    # Sorting
    sort_mapping = {
        "policy_name": AttendancePolicy.policy_name,
        "created_at": AttendancePolicy.created_at,
        "is_active": AttendancePolicy.is_active
    }
    
    sort_field = sort_mapping.get(sort_by.lower(), AttendancePolicy.policy_name)
    
    if order.lower() == "desc":
        query = query.order_by(sort_field.desc())
    else:
        query = query.order_by(sort_field.asc())

    # Pagination
    total_records = query.count()
    total_pages = (total_records + limit - 1) // limit
    skip = (page - 1) * limit

    policies = query.offset(skip).limit(limit).all()

    pagination = {
        "total_records": total_records,
        "current_page": page,
        "total_pages": total_pages,
        "page_size": limit
    }

    return AttendancePolicyListResponse(
        success=True,
        message="Attendance policies retrieved successfully",
        data=[populate_policy_uuids(p, db) for p in policies],
        pagination=pagination
    )

@router.get("/{policy_id}", response_model=AttendancePolicyResponse)
def get_attendance_policy(
    policy_id: str,
    db: Session = Depends(deps.get_db),
    current_org: Organization = Depends(deps.get_current_org),
    _: bool = Depends(deps.check_permission(AttendancePolicyPermissions.READ))
):
    """
    Get detailed information about a specific attendance policy.
    Supports both internal ID and UUID.
    """
    policy = None
    try:
        # Try resolving by UUID first
        uuid_obj = uuid.UUID(policy_id)
        policy = db.query(AttendancePolicy).filter(
            AttendancePolicy.uuid == uuid_obj,
            AttendancePolicy.organization_id == current_org.id,
            AttendancePolicy.is_deleted == False
        ).first()
    except ValueError:
        # Fallback to internal ID
        try:
            policy = db.query(AttendancePolicy).filter(
                AttendancePolicy.id == int(policy_id),
                AttendancePolicy.organization_id == current_org.id,
                AttendancePolicy.is_deleted == False
            ).first()
        except ValueError:
            pass

    if not policy:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Attendance policy not found"
        )

    return AttendancePolicyResponse(
        success=True,
        message="Attendance policy details retrieved successfully",
        data=populate_policy_uuids(policy, db)
    )

@router.put("/{policy_id}", response_model=AttendancePolicyResponse)
def update_attendance_policy(
    policy_id: str,
    policy_in: AttendancePolicyUpdate,
    db: Session = Depends(deps.get_db),
    current_org: Organization = Depends(deps.get_current_org),
    _: bool = Depends(deps.check_permission(AttendancePolicyPermissions.UPDATE))
):
    """
    Update an existing attendance policy.
    """
    # 1. Fetch policy
    policy = None
    try:
        uuid_obj = uuid.UUID(policy_id)
        policy = db.query(AttendancePolicy).filter(
            AttendancePolicy.uuid == uuid_obj,
            AttendancePolicy.organization_id == current_org.id,
            AttendancePolicy.is_deleted == False
        ).first()
    except ValueError:
        try:
            policy = db.query(AttendancePolicy).filter(
                AttendancePolicy.id == int(policy_id),
                AttendancePolicy.organization_id == current_org.id,
                AttendancePolicy.is_deleted == False
            ).first()
        except ValueError:
            pass

    if not policy:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Attendance policy not found"
        )

    # 2. Handle default policy logic
    update_data = policy_in.model_dump(exclude_unset=True)
    if update_data.get("is_default"):
        # Unset existing default policy for this organization
        db.query(AttendancePolicy).filter(
            AttendancePolicy.organization_id == current_org.id,
            AttendancePolicy.id != policy.id,
            AttendancePolicy.is_default == True
        ).update({"is_default": False})

    # 3. Apply updates
    update_data = policy_in.model_dump(exclude_unset=True, exclude={'department_uuids', 'location_uuids', 'departments', 'locations'})
    
    department_uuids = getattr(policy_in, 'department_uuids', None)
    if department_uuids is not None:
        dept_ids = db.query(Department.id).filter(
            Department.uuid.in_(department_uuids),
            Department.organization_id == current_org.id,
            Department.is_deleted == False
        ).all()
        update_data['department_ids'] = [r[0] for r in dept_ids]

    location_uuids = getattr(policy_in, 'location_uuids', None)
    if location_uuids is not None:
        loc_ids = db.query(Location.id).filter(
            Location.uuid.in_(location_uuids),
            Location.organization_id == current_org.id,
            Location.is_deleted == False
        ).all()
        update_data['location_ids'] = [r[0] for r in loc_ids]

    for field, value in update_data.items():
        setattr(policy, field, value)

    try:
        db.commit()
        db.refresh(policy)
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update attendance policy: {str(e)}"
        )

    return AttendancePolicyResponse(
        success=True,
        message="Attendance policy updated successfully",
        data=populate_policy_uuids(policy, db)
    )

@router.delete("/{policy_id}", response_model=dict)
def delete_attendance_policy(
    policy_id: str,
    db: Session = Depends(deps.get_db),
    current_org: Organization = Depends(deps.get_current_org),
    _: bool = Depends(deps.check_permission(AttendancePolicyPermissions.DELETE))
):
    """
    Soft delete an attendance policy.
    """
    policy = None
    try:
        uuid_obj = uuid.UUID(policy_id)
        policy = db.query(AttendancePolicy).filter(
            AttendancePolicy.uuid == uuid_obj,
            AttendancePolicy.organization_id == current_org.id,
            AttendancePolicy.is_deleted == False
        ).first()
    except ValueError:
        try:
            policy = db.query(AttendancePolicy).filter(
                AttendancePolicy.id == int(policy_id),
                AttendancePolicy.organization_id == current_org.id,
                AttendancePolicy.is_deleted == False
            ).first()
        except ValueError:
            pass

    if not policy:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Attendance policy not found"
        )

    # Soft delete
    policy.is_deleted = True
    policy.deleted_at = datetime.utcnow()
    
    if policy.is_default:
        policy.is_default = False

    try:
        db.commit()
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete attendance policy: {str(e)}"
        )

    return {
        "success": True,
        "message": "Attendance policy deleted successfully",
        "data": None
    }
