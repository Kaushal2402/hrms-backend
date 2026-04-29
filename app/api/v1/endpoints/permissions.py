from typing import List, Optional, Any
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import func
import uuid

from app.api import deps
from app.models.organization import Organization
from app.models.rbac import Permission
from app.schemas.rbac import Permission as PermissionSchema, PermissionListResponse, PermissionCreate, PermissionResponse, PermissionUpdate

router = APIRouter()

@router.post("/", response_model=PermissionResponse)
def create_permission(
    permission_in: PermissionCreate,
    db: Session = Depends(deps.get_db),
    current_org: Organization = Depends(deps.get_current_org)
):
    """
    Create a new permission.
    """
    # Check if permission with same code exists
    existing_permission = db.query(Permission).filter(
        Permission.permission_code == permission_in.permission_code
    ).first()

    if existing_permission:
        raise HTTPException(
            status_code=400,
            detail=f"Permission with code '{permission_in.permission_code}' already exists."
        )

    permission = Permission(
        **permission_in.dict()
    )
    
    db.add(permission)
    db.commit()
    db.refresh(permission)

    return PermissionResponse(
        success=True,
        message="Permission created successfully",
        data=PermissionSchema.model_validate(permission)
    )

@router.get("/", response_model=PermissionListResponse)
def get_permissions(
    module: Optional[str] = Query(None, description="Filter by Module"),
    resource: Optional[str] = Query(None, description="Filter by Resource"),
    is_active: Optional[bool] = Query(True, description="Filter by active status"),
    db: Session = Depends(deps.get_db),
    current_org: Organization = Depends(deps.get_current_org)
):
    """
    Get list of available permissions.
    """
    # Permissions are generally global/system-defined but we filter them.
    # If permissions werer org-specific, we'd filter by org_id.
    # Assuming Permission table contains master list of all possible permissions system-wide.
    
    query = db.query(Permission)

    if is_active is not None:
        query = query.filter(Permission.is_active == is_active)
    
    if module:
        query = query.filter(Permission.module == module)
        
    if resource:
        query = query.filter(Permission.resource == resource)

    permissions = query.order_by(Permission.module, Permission.resource, Permission.display_order).all()
    
    schema_permissions = [PermissionSchema.model_validate(perm) for perm in permissions]

    return PermissionListResponse(
        success=True,
        message="Permissions retrieved successfully",
        total_permissions=len(schema_permissions),
        data=schema_permissions
    )

@router.put("/{permission_uuid}", response_model=PermissionResponse)
def update_permission(
    permission_uuid: uuid.UUID,
    permission_in: PermissionUpdate,
    db: Session = Depends(deps.get_db),
    current_org: Organization = Depends(deps.get_current_org)
):
    """
    Update permission by UUID.
    """
    permission = db.query(Permission).filter(
        Permission.uuid == permission_uuid
    ).first()

    if not permission:
        raise HTTPException(
            status_code=404,
            detail="Permission not found"
        )
    
    # Check if updating permission_code causes conflict
    if permission_in.permission_code and permission_in.permission_code != permission.permission_code:
        existing_permission = db.query(Permission).filter(
            Permission.permission_code == permission_in.permission_code
        ).first()

        if existing_permission:
            raise HTTPException(
                status_code=400,
                detail=f"Permission with code '{permission_in.permission_code}' already exists."
            )

    update_data = permission_in.dict(exclude_unset=True)
    for field, value in update_data.items():
        setattr(permission, field, value)
    
    db.commit()
    db.refresh(permission)

    return PermissionResponse(
        success=True,
        message="Permission updated successfully",
        data=PermissionSchema.model_validate(permission)
    )
