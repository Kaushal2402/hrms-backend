import uuid
from typing import List, Optional, Union
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from sqlalchemy import or_

from app.api import deps
from app.models.organization import Organization
from app.models.employee import Employee
from app.models.performance import GoalFramework
from app.schemas.performance_goal_frameworks import (
    GoalFrameworkCreate, GoalFrameworkUpdate, GoalFrameworkSchema, 
    GoalFrameworkResponse, GoalFrameworkListResponse
)

router = APIRouter()
lookup_router = APIRouter()

class PerformancePermissions:
    READ = "201"
    CREATE = "202"
    UPDATE = "203"
    DELETE = "204"

def _get_org_id(current_user: Union[Organization, Employee]) -> int:
    return current_user.id if isinstance(current_user, Organization) else current_user.organization_id

def _require_permission(db, current_user, code, action_label):
    if isinstance(current_user, Organization):
        return
    if not deps.has_permission(db, current_user, code):
        raise HTTPException(status_code=403, detail=f"You do not have permission to {action_label}")

@router.get("/", response_model=GoalFrameworkListResponse)
def get_goal_frameworks(
    page: int = Query(1, ge=1),
    limit: int = Query(10, ge=1, le=100),
    framework_type: Optional[str] = None,
    is_active: Optional[bool] = None,
    search: Optional[str] = None,
    sort_by: Optional[str] = Query(None),
    sort_order: Optional[str] = Query(None),
    db: Session = Depends(deps.get_db),
    current_user: Union[Organization, Employee] = Depends(deps.get_current_user),
    current_org: Organization = Depends(deps.get_current_org)
):
    _require_permission(db, current_user, PerformancePermissions.READ, "list goal frameworks")
    query = db.query(GoalFramework).filter(GoalFramework.organization_id == current_org.id)
    
    if framework_type:
        query = query.filter(GoalFramework.framework_type == framework_type)
    if is_active is not None:
        query = query.filter(GoalFramework.is_active == is_active)
    if search:
        query = query.filter(GoalFramework.name.ilike(f"%{search}%"))

    # Sorting
    if sort_by:
        if sort_by == "name":
            sort_attr = GoalFramework.name
        elif sort_by == "created_at":
            sort_attr = GoalFramework.created_at
        else:
            sort_attr = GoalFramework.created_at
            
        if sort_order == "desc":
            query = query.order_by(sort_attr.desc())
        else:
            query = query.order_by(sort_attr.asc())
    else:
        # Default sort
        query = query.order_by(GoalFramework.created_at.desc())
        
    total_records = query.count()
    items = query.offset((page - 1) * limit).limit(limit).all()
    
    return GoalFrameworkListResponse(
        success=True, message="Goal frameworks retrieved successfully",
        data=items, pagination={'total_records': total_records, 'current_page': page, 
                                'total_pages': (total_records + limit - 1) // limit if total_records > 0 else 0, 
                                'page_size': limit}
    )

@router.post("/", response_model=GoalFrameworkResponse)
def create_goal_framework(
    item_in: GoalFrameworkCreate,
    db: Session = Depends(deps.get_db),
    current_user: Union[Organization, Employee] = Depends(deps.get_current_user),
    current_org: Organization = Depends(deps.get_current_org)
):
    _require_permission(db, current_user, PerformancePermissions.CREATE, "create goal framework")
    org_id = _get_org_id(current_user)
    
    if db.query(GoalFramework).filter(GoalFramework.organization_id == org_id, GoalFramework.name == item_in.name).first():
        raise HTTPException(400, "Framework name already exists")
        
    item = GoalFramework(organization_id=org_id, created_by=current_user.id if not isinstance(current_user, Organization) else None, **item_in.model_dump())
    db.add(item)
    db.commit()
    db.refresh(item)
    return {"success": True, "message": "Goal framework created successfully", "data": item}

@router.get("/{framework_uuid}", response_model=GoalFrameworkResponse)
def get_goal_framework(
    framework_uuid: uuid.UUID,
    db: Session = Depends(deps.get_db),
    current_user: Union[Organization, Employee] = Depends(deps.get_current_user),
    current_org: Organization = Depends(deps.get_current_org)
):
    _require_permission(db, current_user, PerformancePermissions.READ, "view goal framework")
    item = db.query(GoalFramework).filter(GoalFramework.uuid == framework_uuid, GoalFramework.organization_id == current_org.id).first()
    if not item: raise HTTPException(404, "Goal framework not found")
    return {"success": True, "message": "Goal framework retrieved successfully", "data": item}

@router.put("/{framework_uuid}", response_model=GoalFrameworkResponse)
def update_goal_framework(
    framework_uuid: uuid.UUID,
    item_in: GoalFrameworkUpdate,
    db: Session = Depends(deps.get_db),
    current_user: Union[Organization, Employee] = Depends(deps.get_current_user),
    current_org: Organization = Depends(deps.get_current_org)
):
    _require_permission(db, current_user, PerformancePermissions.UPDATE, "update goal framework")
    item = db.query(GoalFramework).filter(GoalFramework.uuid == framework_uuid, GoalFramework.organization_id == current_org.id).first()
    if not item: raise HTTPException(404, "Goal framework not found")
    
    for field, value in item_in.model_dump(exclude_unset=True).items():
        setattr(item, field, value)
    db.commit()
    db.refresh(item)
    return {"success": True, "message": "Goal framework updated successfully", "data": item}

@router.patch("/{framework_uuid}/set-default", response_model=GoalFrameworkResponse)
def set_default_framework(
    framework_uuid: uuid.UUID,
    db: Session = Depends(deps.get_db),
    current_user: Union[Organization, Employee] = Depends(deps.get_current_user),
    current_org: Organization = Depends(deps.get_current_org)
):
    _require_permission(db, current_user, PerformancePermissions.UPDATE, "set default framework")
    db.query(GoalFramework).filter(GoalFramework.organization_id == current_org.id).update({"is_default": False})
    item = db.query(GoalFramework).filter(GoalFramework.uuid == framework_uuid, GoalFramework.organization_id == current_org.id).first()
    if not item: raise HTTPException(404, "Goal framework not found")
    item.is_default = True
    db.commit()
    db.refresh(item)
    return {"success": True, "message": "Default framework updated successfully", "data": item}

@router.delete("/{framework_uuid}")
def delete_goal_framework(
    framework_uuid: uuid.UUID,
    db: Session = Depends(deps.get_db),
    current_user: Union[Organization, Employee] = Depends(deps.get_current_user),
    current_org: Organization = Depends(deps.get_current_org)
):
    _require_permission(db, current_user, PerformancePermissions.DELETE, "delete goal framework")
    item = db.query(GoalFramework).filter(GoalFramework.uuid == framework_uuid, GoalFramework.organization_id == current_org.id).first()
    if not item: raise HTTPException(404, "Goal framework not found")
    db.delete(item)
    db.commit()
    return {"success": True, "message": "Goal framework deleted successfully"}

@lookup_router.get("", response_model=GoalFrameworkListResponse)
def list_goal_frameworks_lookup(
    page: int = Query(1, ge=1),
    limit: int = Query(10, ge=1, le=100),
    framework_type: Optional[str] = None,
    is_active: Optional[bool] = None,
    search: Optional[str] = None,
    sort_by: Optional[str] = Query(None),
    sort_order: Optional[str] = Query(None),
    db: Session = Depends(deps.get_db),
    current_user: Union[Organization, Employee] = Depends(deps.get_current_user),
    current_org: Organization = Depends(deps.get_current_org)
):
    query = db.query(GoalFramework).filter(GoalFramework.organization_id == current_org.id)
    
    if framework_type:
        query = query.filter(GoalFramework.framework_type == framework_type)
    if is_active is not None:
        query = query.filter(GoalFramework.is_active == is_active)
    if search:
        query = query.filter(GoalFramework.name.ilike(f"%{search}%"))

    # Sorting
    if sort_by:
        if sort_by == "name":
            sort_attr = GoalFramework.name
        elif sort_by == "created_at":
            sort_attr = GoalFramework.created_at
        else:
            sort_attr = GoalFramework.created_at
            
        if sort_order == "desc":
            query = query.order_by(sort_attr.desc())
        else:
            query = query.order_by(sort_attr.asc())
    else:
        # Default sort
        query = query.order_by(GoalFramework.created_at.desc())
        
    total_records = query.count()
    items = query.offset((page - 1) * limit).limit(limit).all()
    
    return GoalFrameworkListResponse(
        success=True, message="Goal frameworks retrieved successfully",
        data=items, pagination={'total_records': total_records, 'current_page': page, 
                                'total_pages': (total_records + limit - 1) // limit if total_records > 0 else 0, 
                                'page_size': limit}
    )