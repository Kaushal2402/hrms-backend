from typing import List, Optional, Any
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import func
import uuid

from app.api import deps
from app.models.organization import Organization
from app.models.rbac import Role, Permission, RolePermission, RoleType
from app.schemas.rbac import (
    Role as RoleSchema, 
    RoleListResponse, 
    RoleCreate, 
    RoleUpdate, 
    RoleResponse,
    Permission as PermissionSchema,
    PermissionListResponse,
    RolePermissionUpdate,
    RolePermissionListResponse,
    RoleTypeCreate,
    RoleTypeUpdate,
    RoleTypeResponse,
    RoleTypeListResponse,
    RoleTypeSchema
)

router = APIRouter()

@router.post("/types", response_model=RoleTypeResponse)
def create_role_type(
    type_in: RoleTypeCreate,
    db: Session = Depends(deps.get_db),
    current_user: Any = Depends(deps.get_current_user)
):
    """
    Create a new role type.
    """
    if db.query(RoleType).filter(RoleType.name == type_in.name).first():
        raise HTTPException(status_code=400, detail="Role type already exists")
        
    db_obj = RoleType(**type_in.model_dump())
    db.add(db_obj)
    db.commit()
    db.refresh(db_obj)
    
    return {
        "success": True,
        "message": "Role type created successfully",
        "data": RoleTypeSchema.model_validate(db_obj).model_dump()
    }

@router.put("/types/{type_id}", response_model=RoleTypeResponse)
def update_role_type(
    type_id: int,
    type_in: RoleTypeUpdate,
    db: Session = Depends(deps.get_db),
    current_user: Any = Depends(deps.get_current_user)
):
    """
    Update an existing role type.
    """
    db_obj = db.query(RoleType).filter(RoleType.id == type_id).first()
    if not db_obj:
        raise HTTPException(status_code=404, detail="Role type not found")
        
    if type_in.name and type_in.name != db_obj.name:
        if db.query(RoleType).filter(RoleType.name == type_in.name).first():
            raise HTTPException(status_code=400, detail="Role type name already exists")
            
    for key, value in type_in.model_dump(exclude_unset=True).items():
        setattr(db_obj, key, value)
        
    db.commit()
    db.refresh(db_obj)
    
    return {
        "success": True,
        "message": "Role type updated successfully",
        "data": RoleTypeSchema.model_validate(db_obj).model_dump()
    }

@router.get("/types", response_model=RoleTypeListResponse)
def get_role_types(
    db: Session = Depends(deps.get_db),
    current_user: Any = Depends(deps.get_current_user)
):
    """
    Get all active role types.
    """
    types = db.query(RoleType).filter(RoleType.is_active == True).all()
    return {
        "success": True,
        "message": "Role types retrieved successfully",
        "data": [RoleTypeSchema.model_validate(t) for t in types]
    }

@router.post("/", response_model=RoleResponse)
def create_role(
    role_in: RoleCreate,
    db: Session = Depends(deps.get_db),
    current_org: Organization = Depends(deps.get_current_org)
):
    """
    Create a new role.
    """
    # Check if role with same code exists in organization
    existing_role = db.query(Role).filter(
        Role.organization_id == current_org.id,
        Role.role_code == role_in.role_code,
        Role.is_deleted == False
    ).first()

    if existing_role:
        raise HTTPException(
            status_code=400,
            detail=f"Role with code '{role_in.role_code}' already exists."
        )

    role = Role(
        organization_id=current_org.id,
        **role_in.dict()
    )
    
    db.add(role)
    db.commit()
    db.refresh(role)

    return RoleResponse(
        success=True,
        message="Role created successfully",
        data=RoleSchema.model_validate(role)
    )

@router.get("/lookup")
def lookup_roles(
    db: Session = Depends(deps.get_db),
    current_org: Organization = Depends(deps.get_current_org),
    search: Optional[str] = Query(None, description="Search by role name or code"),
    limit: int = Query(100, ge=1, description="Limit lookup results")
):
    """
    Lite lookup endpoint for roles (UUID, Role Name, Role Code).
    Accessible to all authenticated users for filters/dropdowns.
    """
    query = db.query(Role).filter(
        Role.organization_id == current_org.id,
        Role.is_active == True,
        Role.is_deleted == False
    )
    
    if search:
        search_term = f"%{search}%"
        query = query.filter(
            (Role.role_name.ilike(search_term)) |
            (Role.role_code.ilike(search_term))
        )
        
    roles = query.order_by(Role.role_name.asc()).limit(limit).all()
    
    return {
        "success": True,
        "data": [
            {
                "uuid": role.uuid, 
                "role_name": role.role_name,
                "role_code": role.role_code
            } for role in roles
        ]
    }

@router.get("/", response_model=RoleListResponse)
def get_roles(
    is_active: Optional[bool] = Query(None, description="Filter by active status"),
    scope: Optional[str] = Query(None, description="Filter by role scope (system, organization, etc.)"),
    role_type_id: Optional[int] = Query(None, description="Filter by role type ID"),
    sort_by: Optional[str] = Query("role_name", description="Field to sort by"),
    sort_order: Optional[str] = Query("asc", regex="^(asc|desc)$", description="Sort order (asc or desc)"),
    page: int = Query(1, ge=1),
    limit: int = Query(10, ge=1, le=100),
    search: Optional[str] = Query(None, description="Search by role name or code"),
    db: Session = Depends(deps.get_db),
    current_org: Organization = Depends(deps.get_current_org)
):
    """
    Get list of roles.
    """
    query = db.query(Role).filter(
        Role.organization_id == current_org.id,
        Role.is_deleted == False
    )

    if is_active is not None:
        query = query.filter(Role.is_active == is_active)
    
    if scope:
        query = query.filter(Role.scope == scope)
    
    if role_type_id:
        query = query.filter(Role.role_type_id == role_type_id)

    if search:
        search_term = f"%{search}%"
        query = query.filter(
            (Role.role_name.ilike(search_term)) |
            (Role.role_code.ilike(search_term))
        )

    # Apply sorting
    if sort_by:
        allowed_sort_fields = ["role_code", "role_name", "role_type_id", "role_type", "scope", "role_level", "is_active"]
        if sort_by in allowed_sort_fields:
            if sort_by == "role_type":
                query = query.join(RoleType, Role.role_type_id == RoleType.id)
                sort_attr = RoleType.name
            else:
                sort_attr = getattr(Role, sort_by)
                
            if sort_order == "desc":
                query = query.order_by(sort_attr.desc())
            else:
                query = query.order_by(sort_attr.asc())
    else:
        # Default sorting
        query = query.order_by(Role.role_name.asc())

    total_records = query.count()
    total_pages = (total_records + limit - 1) // limit if total_records > 0 else 0
    
    roles = query.offset((page - 1) * limit).limit(limit).all()
    
    schema_roles = [RoleSchema.model_validate(role) for role in roles]

    pagination_data = {
        "total_records": total_records,
        "current_page": page,
        "total_pages": total_pages,
        "page_size": limit
    }

    return RoleListResponse(
        success=True,
        message="Roles retrieved successfully",
        data=schema_roles,
        pagination=pagination_data
    )

@router.get("/{role_uuid}", response_model=RoleResponse)
def get_role_details(
    role_uuid: uuid.UUID,
    db: Session = Depends(deps.get_db),
    current_org: Organization = Depends(deps.get_current_org)
):
    """
    Get role details by UUID.
    """
    role = db.query(Role).filter(
        Role.organization_id == current_org.id,
        Role.uuid == role_uuid,
        Role.is_deleted == False
    ).first()

    if not role:
        raise HTTPException(
            status_code=404,
            detail="Role not found"
        )
    
    return RoleResponse(
        success=True,
        message="Role details retrieved successfully",
        data=RoleSchema.model_validate(role)
    )

@router.put("/{role_uuid}", response_model=RoleResponse)
def update_role(
    role_uuid: uuid.UUID,
    role_in: RoleUpdate,
    db: Session = Depends(deps.get_db),
    current_org: Organization = Depends(deps.get_current_org)
):
    """
    Update role by UUID.
    """
    role = db.query(Role).filter(
        Role.organization_id == current_org.id,
        Role.uuid == role_uuid,
        Role.is_deleted == False
    ).first()

    if not role:
        raise HTTPException(
            status_code=404,
            detail="Role not found"
        )
    
    if role.is_system_role:
        raise HTTPException(
            status_code=400,
            detail="System roles cannot be modified"
        )
    
    # Check if updating role_code causes conflict
    if role_in.role_code and role_in.role_code != role.role_code:
        existing_role = db.query(Role).filter(
            Role.organization_id == current_org.id,
            Role.role_code == role_in.role_code,
            Role.is_deleted == False
        ).first()

        if existing_role:
            raise HTTPException(
                status_code=400,
                detail=f"Role with code '{role_in.role_code}' already exists."
            )

    update_data = role_in.dict(exclude_unset=True)
    for field, value in update_data.items():
        setattr(role, field, value)
    
    db.commit()
    db.refresh(role)

    return RoleResponse(
        success=True,
        message="Role updated successfully",
        data=RoleSchema.model_validate(role)
    )

@router.delete("/{role_uuid}")
def delete_role(
    role_uuid: uuid.UUID,
    db: Session = Depends(deps.get_db),
    current_org: Organization = Depends(deps.get_current_org)
):
    """
    Soft delete role by UUID.
    """
    role = db.query(Role).filter(
        Role.organization_id == current_org.id,
        Role.uuid == role_uuid,
        Role.is_deleted == False
    ).first()

    if not role:
        raise HTTPException(
            status_code=404,
            detail="Role not found"
        )
    
    if role.is_system_role:
        raise HTTPException(
            status_code=400,
            detail="System roles cannot be deleted"
        )
    
    # Check if role is assigned to any active users
    if role.users:
        # Filter for active user assignments
        active_assignments = [ur for ur in role.users if ur.is_active]
        if active_assignments:
             raise HTTPException(
                status_code=400,
                detail="Cannot delete role assigned to active users"
            )

    role.is_deleted = True
    role.deleted_at = func.now()
    role.is_active = False # Deactivate role as well
    
    db.commit()

    return {
        "success": True,
        "message": "Role deleted successfully"
    }

@router.get("/{role_uuid}/permissions", response_model=RolePermissionListResponse)
def get_role_permissions(
    role_uuid: uuid.UUID,
    db: Session = Depends(deps.get_db),
    current_org: Organization = Depends(deps.get_current_org)
):
    """
    Get all available permissions with assigned status for a role.
    """
    role = db.query(Role).filter(
        Role.organization_id == current_org.id,
        Role.uuid == role_uuid,
        Role.is_deleted == False
    ).first()

    if not role:
        raise HTTPException(status_code=404, detail="Role not found")

    # Get all active permissions
    all_permissions = db.query(Permission).filter(Permission.is_active == True).all()

    # Get IDs of currently assigned permissions
    assigned_permission_ids = [rp.permission_id for rp in role.permissions]

    role_permissions_data = []
    for permission in all_permissions:
        role_permissions_data.append({
            "permission": PermissionSchema.model_validate(permission),
            "is_given": permission.id in assigned_permission_ids
        })

    return RolePermissionListResponse(
        success=True,
        message="Role permissions retrieved successfully",
        data=role_permissions_data
    )

@router.put("/{role_uuid}/permissions")
def update_role_permissions(
    role_uuid: uuid.UUID,
    permission_in: RolePermissionUpdate,
    db: Session = Depends(deps.get_db),
    current_org: Organization = Depends(deps.get_current_org)
):
    """
    Update (sync) permissions for a role.
    """
    role = db.query(Role).filter(
        Role.organization_id == current_org.id,
        Role.uuid == role_uuid,
        Role.is_deleted == False
    ).first()

    if not role:
        raise HTTPException(status_code=404, detail="Role not found")
    
    if role.is_system_role:
        raise HTTPException(status_code=400, detail="System roles cannot be modified")

    # Get actual permission records for the provided UUIDs
    requested_permissions = db.query(Permission).filter(
        Permission.uuid.in_(permission_in.permission_uuids),
        Permission.is_active == True
    ).all()

    # Clear existing role-permission bindings
    db.query(RolePermission).filter(RolePermission.role_id == role.id).delete()

    # Add new role-permission bindings
    for permission in requested_permissions:
        new_rp = RolePermission(
            role_id=role.id,
            permission_id=permission.id,
            grant_type='allow',
            is_active=True
        )
        db.add(new_rp)
    
    db.commit()

    return {
        "success": True,
        "message": "Role permissions updated successfully"
    }
