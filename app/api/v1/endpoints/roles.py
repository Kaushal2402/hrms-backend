from typing import List, Optional, Any, Union
from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
from sqlalchemy import func
import uuid

from app.api import deps
from app.core.permissions import RolePermissions
from app.models.organization import Organization
from app.models.employee import Employee
from app.models.rbac import Role, Permission, RolePermission, RoleType, UserRole
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

# ---------------------------------------------------------------------------
# Permission Codes for this module (from RolePermissions in permissions.py):
#   RolePermissions.READ   = "71"  → GET list, details, role permissions
#   RolePermissions.CREATE = "72"  → POST /roles
#   RolePermissions.UPDATE = "73"  → PUT /roles/{uuid}, PUT permissions
#   RolePermissions.DELETE = "74"  → DELETE /roles/{uuid}
#
# /roles/lookup  - Open (no RBAC permission required — auth only)
# /roles/types   - Org login only (no employee access)
# ---------------------------------------------------------------------------


# ============================================================
# HELPER — resolve org_id from any authenticated user
# ============================================================
def _get_org_id(current_user: Union[Organization, Employee]) -> int:
    if isinstance(current_user, Organization):
        return current_user.id
    return current_user.organization_id


def _require_permission(
    db: Session,
    current_user: Union[Organization, Employee],
    code: str,
    action_label: str
) -> None:
    """
    Raises 403 if an Employee does not hold the given permission code.
    Organization users are always allowed (super-user bypass).
    """
    if isinstance(current_user, Organization):
        return  # Org → full bypass
    if not deps.has_permission(db, current_user, code):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"You do not have permission to {action_label} roles (requires code: {code})"
        )


# ============================================================
# ROLE TYPES — Org admin only
# ============================================================

@router.post("/types", response_model=RoleTypeResponse)
def create_role_type(
    type_in: RoleTypeCreate,
    db: Session = Depends(deps.get_db),
    current_user: Union[Organization, Employee] = Depends(deps.get_current_user)
):
    """
    Create a new role type. Organization login only.
    """
    if not isinstance(current_user, Organization):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only organization admins can manage role types"
        )

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
    current_user: Union[Organization, Employee] = Depends(deps.get_current_user)
):
    """
    Update a role type. Organization login only.
    """
    if not isinstance(current_user, Organization):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only organization admins can manage role types"
        )

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
    current_user: Union[Organization, Employee] = Depends(deps.get_current_user)
):
    """
    Get all active role types. Accessible to all authenticated users.
    """
    org_id = _get_org_id(current_user)
    types = db.query(RoleType).filter(RoleType.is_active == True).all()
    return {
        "success": True,
        "message": "Role types retrieved successfully",
        "data": [RoleTypeSchema.model_validate(t) for t in types]
    }


# ============================================================
# OPEN LOOKUP — No RBAC permission required
# ============================================================

@router.get("/lookup")
def lookup_roles(
    db: Session = Depends(deps.get_db),
    current_user: Union[Organization, Employee] = Depends(deps.get_current_user),
    search: Optional[str] = Query(None, description="Search by role name or code"),
    limit: int = Query(100, ge=1, description="Limit lookup results")
):
    """
    Lightweight lookup endpoint (UUID, Role Name, Role Code).
    No RBAC permission required — only authentication.
    Intended for use in dropdowns/filters across all modules.
    """
    org_id = _get_org_id(current_user)

    query = db.query(Role).filter(
        Role.organization_id == org_id,
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
        "message": "Roles lookup retrieved successfully",
        "data": [
            {
                "uuid": role.uuid,
                "role_name": role.role_name,
                "role_code": role.role_code
            }
            for role in roles
        ]
    }


# ============================================================
# LIST ROLES — Permission 71 (Read)
# ============================================================

@router.get("/", response_model=RoleListResponse)
def get_roles(
    is_active: Optional[bool] = Query(None, description="Filter by active status"),
    scope: Optional[str] = Query(None, description="Filter by role scope"),
    role_type_id: Optional[int] = Query(None, description="Filter by role type ID"),
    sort_by: Optional[str] = Query("role_name", description="Field to sort by"),
    sort_order: Optional[str] = Query("asc", regex="^(asc|desc)$"),
    page: int = Query(1, ge=1),
    limit: int = Query(10, ge=1, le=100),
    search: Optional[str] = Query(None, description="Search by role name or code"),
    db: Session = Depends(deps.get_db),
    current_user: Union[Organization, Employee] = Depends(deps.get_current_user)
):
    """
    List all roles for the organization.
    Requires permission 71 for employees.
    """
    _require_permission(db, current_user, RolePermissions.READ, "list")
    org_id = _get_org_id(current_user)

    query = db.query(Role).filter(
        Role.organization_id == org_id,
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

    allowed_sort_fields = ["role_code", "role_name", "role_type_id", "role_type", "scope", "role_level", "is_active"]
    if sort_by in allowed_sort_fields:
        if sort_by == "role_type":
            query = query.join(RoleType, Role.role_type_id == RoleType.id)
            sort_attr = RoleType.name
        else:
            sort_attr = getattr(Role, sort_by)
        query = query.order_by(sort_attr.desc() if sort_order == "desc" else sort_attr.asc())
    else:
        query = query.order_by(Role.role_name.asc())

    total_records = query.count()
    total_pages = (total_records + limit - 1) // limit if total_records > 0 else 0
    roles = query.offset((page - 1) * limit).limit(limit).all()

    return RoleListResponse(
        success=True,
        message="Roles retrieved successfully",
        data=[RoleSchema.model_validate(r) for r in roles],
        pagination={
            "total_records": total_records,
            "current_page": page,
            "total_pages": total_pages,
            "page_size": limit
        }
    )


# ============================================================
# GET ROLE DETAILS — Permission 71 (Read)
# ============================================================

@router.get("/{role_uuid}", response_model=RoleResponse)
def get_role_details(
    role_uuid: uuid.UUID,
    db: Session = Depends(deps.get_db),
    current_user: Union[Organization, Employee] = Depends(deps.get_current_user)
):
    """
    Get role details by UUID.
    Requires permission 71 for employees.
    """
    _require_permission(db, current_user, RolePermissions.READ, "view")
    org_id = _get_org_id(current_user)

    role = db.query(Role).filter(
        Role.organization_id == org_id,
        Role.uuid == role_uuid,
        Role.is_deleted == False
    ).first()

    if not role:
        raise HTTPException(status_code=404, detail="Role not found")

    return RoleResponse(
        success=True,
        message="Role details retrieved successfully",
        data=RoleSchema.model_validate(role)
    )


# ============================================================
# CREATE ROLE — Permission 72 (Create)
# ============================================================

@router.post("/", response_model=RoleResponse)
def create_role(
    role_in: RoleCreate,
    db: Session = Depends(deps.get_db),
    current_user: Union[Organization, Employee] = Depends(deps.get_current_user)
):
    """
    Create a new role.
    Requires permission 72 for employees.
    """
    _require_permission(db, current_user, RolePermissions.CREATE, "create")
    org_id = _get_org_id(current_user)

    existing_role = db.query(Role).filter(
        Role.organization_id == org_id,
        Role.role_code == role_in.role_code,
        Role.is_deleted == False
    ).first()

    if existing_role:
        raise HTTPException(
            status_code=400,
            detail=f"Role with code '{role_in.role_code}' already exists."
        )

    role = Role(
        organization_id=org_id,
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


# ============================================================
# UPDATE ROLE — Permission 73 (Update)
# ============================================================

@router.put("/{role_uuid}", response_model=RoleResponse)
def update_role(
    role_uuid: uuid.UUID,
    role_in: RoleUpdate,
    db: Session = Depends(deps.get_db),
    current_user: Union[Organization, Employee] = Depends(deps.get_current_user)
):
    """
    Update role by UUID.
    Requires permission 73 for employees.
    """
    _require_permission(db, current_user, RolePermissions.UPDATE, "update")
    org_id = _get_org_id(current_user)

    role = db.query(Role).filter(
        Role.organization_id == org_id,
        Role.uuid == role_uuid,
        Role.is_deleted == False
    ).first()

    if not role:
        raise HTTPException(status_code=404, detail="Role not found")

    if role.is_system_role:
        raise HTTPException(status_code=400, detail="System roles cannot be modified")

    if role_in.role_code and role_in.role_code != role.role_code:
        if db.query(Role).filter(
            Role.organization_id == org_id,
            Role.role_code == role_in.role_code,
            Role.is_deleted == False
        ).first():
            raise HTTPException(
                status_code=400,
                detail=f"Role with code '{role_in.role_code}' already exists."
            )

    for field, value in role_in.dict(exclude_unset=True).items():
        setattr(role, field, value)

    db.commit()
    db.refresh(role)

    return RoleResponse(
        success=True,
        message="Role updated successfully",
        data=RoleSchema.model_validate(role)
    )


# ============================================================
# DELETE ROLE — Permission 74 (Delete)
# ============================================================

@router.delete("/{role_uuid}")
def delete_role(
    role_uuid: uuid.UUID,
    db: Session = Depends(deps.get_db),
    current_user: Union[Organization, Employee] = Depends(deps.get_current_user)
):
    """
    Soft delete role by UUID.
    Requires permission 74 for employees.
    """
    _require_permission(db, current_user, RolePermissions.DELETE, "delete")
    org_id = _get_org_id(current_user)

    role = db.query(Role).filter(
        Role.organization_id == org_id,
        Role.uuid == role_uuid,
        Role.is_deleted == False
    ).first()

    if not role:
        raise HTTPException(status_code=404, detail="Role not found")

    if role.is_system_role:
        raise HTTPException(status_code=400, detail="System roles cannot be deleted")

    active_assignments = [ur for ur in role.users if ur.is_active]
    if active_assignments:
        raise HTTPException(
            status_code=400,
            detail="Cannot delete role assigned to active users"
        )

    role.is_deleted = True
    role.deleted_at = func.now()
    role.is_active = False
    db.commit()

    return {
        "success": True,
        "message": "Role deleted successfully"
    }


# ============================================================
# GET ROLE PERMISSIONS — Permission 71 (Read)
# ============================================================

@router.get("/{role_uuid}/permissions", response_model=RolePermissionListResponse)
def get_role_permissions(
    role_uuid: uuid.UUID,
    db: Session = Depends(deps.get_db),
    current_user: Union[Organization, Employee] = Depends(deps.get_current_user)
):
    """
    Get all permissions with assigned status for a role.
    Requires permission 71 for employees.
    """
    _require_permission(db, current_user, RolePermissions.READ, "view permissions of")
    org_id = _get_org_id(current_user)

    role = db.query(Role).filter(
        Role.organization_id == org_id,
        Role.uuid == role_uuid,
        Role.is_deleted == False
    ).first()

    if not role:
        raise HTTPException(status_code=404, detail="Role not found")

    all_permissions = db.query(Permission).filter(Permission.is_active == True).all()
    assigned_ids = [rp.permission_id for rp in role.permissions]

    role_permissions_data = [
        {
            "permission": PermissionSchema.model_validate(p),
            "is_given": p.id in assigned_ids
        }
        for p in all_permissions
    ]

    return RolePermissionListResponse(
        success=True,
        message="Role permissions retrieved successfully",
        data=role_permissions_data
    )


# ============================================================
# UPDATE ROLE PERMISSIONS — Permission 73 (Update)
# ============================================================

@router.put("/{role_uuid}/permissions")
def update_role_permissions(
    role_uuid: uuid.UUID,
    permission_in: RolePermissionUpdate,
    db: Session = Depends(deps.get_db),
    current_user: Union[Organization, Employee] = Depends(deps.get_current_user)
):
    """
    Sync permissions for a role (full replace).
    Requires permission 73 for employees.
    """
    _require_permission(db, current_user, RolePermissions.UPDATE, "update permissions of")
    org_id = _get_org_id(current_user)

    role = db.query(Role).filter(
        Role.organization_id == org_id,
        Role.uuid == role_uuid,
        Role.is_deleted == False
    ).first()

    if not role:
        raise HTTPException(status_code=404, detail="Role not found")

    if role.is_system_role:
        raise HTTPException(status_code=400, detail="System roles cannot be modified")

    requested_permissions = db.query(Permission).filter(
        Permission.uuid.in_(permission_in.permission_uuids),
        Permission.is_active == True
    ).all()

    db.query(RolePermission).filter(RolePermission.role_id == role.id).delete()

    for permission in requested_permissions:
        db.add(RolePermission(
            role_id=role.id,
            permission_id=permission.id,
            grant_type='allow',
            is_active=True
        ))

    db.commit()

    return {
        "success": True,
        "message": "Role permissions updated successfully"
    }
