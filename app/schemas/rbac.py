from typing import Optional, List
from pydantic import BaseModel, UUID4, constr
from datetime import datetime
from app.schemas.department import PaginationData

class RoleTypeBase(BaseModel):
    name: constr(min_length=1, max_length=100)
    description: Optional[str] = None
    is_active: Optional[bool] = True

class RoleTypeCreate(RoleTypeBase):
    pass

class RoleTypeUpdate(BaseModel):
    name: Optional[constr(min_length=1, max_length=100)] = None
    description: Optional[str] = None
    is_active: Optional[bool] = None

class RoleTypeResponse(BaseModel):
    success: bool
    message: str
    data: Optional[dict] = None

class RoleTypeSchema(RoleTypeBase):
    id: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

class RoleTypeListResponse(BaseModel):
    success: bool
    message: str
    data: List[RoleTypeSchema]

class RoleBase(BaseModel):
    role_code: constr(min_length=1, max_length=100)
    role_name: constr(min_length=1, max_length=150)
    role_description: Optional[str] = None
    role_type_id: Optional[int] = None
    parent_role_id: Optional[int] = None
    role_level: Optional[int] = 0
    scope: Optional[str] = 'organization'
    is_active: Optional[bool] = True
    is_system_role: Optional[bool] = False
    is_default: Optional[bool] = False
    inherit_permissions: Optional[bool] = True
    display_order: Optional[int] = 0
    color_code: Optional[str] = None
    icon: Optional[str] = None

class RoleCreate(RoleBase):
    pass

class RoleUpdate(BaseModel):
    role_code: Optional[constr(min_length=1, max_length=100)] = None
    role_name: Optional[constr(min_length=1, max_length=150)] = None
    role_description: Optional[str] = None
    role_type_id: Optional[int] = None
    parent_role_id: Optional[int] = None
    role_level: Optional[int] = None
    scope: Optional[str] = None
    is_active: Optional[bool] = None
    is_system_role: Optional[bool] = None
    is_default: Optional[bool] = None
    inherit_permissions: Optional[bool] = None
    display_order: Optional[int] = None
    color_code: Optional[str] = None
    icon: Optional[str] = None

class RoleInDBBase(RoleBase):
    id: int
    uuid: UUID4
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    created_by: Optional[int] = None
    updated_by: Optional[int] = None

    class Config:
        from_attributes = True

class Role(RoleInDBBase):
    role_type: Optional[RoleTypeSchema] = None

class RoleListResponse(BaseModel):
    success: bool
    message: str
    data: List[Role]
    pagination: Optional[PaginationData] = None

class RoleResponse(BaseModel):
    success: bool
    message: str
    data: Role

class PermissionBase(BaseModel):
    permission_code: constr(min_length=1, max_length=150)
    permission_name: constr(min_length=1, max_length=200)
    permission_description: Optional[str] = None
    resource: str
    action: str
    module: str
    sub_module: Optional[str] = None
    permission_type: Optional[str] = 'standard'
    risk_level: Optional[str] = 'low'
    is_system_permission: Optional[bool] = False
    is_active: Optional[bool] = True
    category: Optional[str] = None

class PermissionCreate(PermissionBase):
    pass

class PermissionUpdate(BaseModel):
    permission_code: Optional[constr(min_length=1, max_length=150)] = None
    permission_name: Optional[constr(min_length=1, max_length=200)] = None
    permission_description: Optional[str] = None
    resource: Optional[str] = None
    action: Optional[str] = None
    module: Optional[str] = None
    sub_module: Optional[str] = None
    permission_type: Optional[str] = None
    risk_level: Optional[str] = None
    is_system_permission: Optional[bool] = None
    is_active: Optional[bool] = None
    category: Optional[str] = None


class PermissionInDBBase(PermissionBase):
    id: int
    uuid: UUID4
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True

class Permission(PermissionInDBBase):
    pass

class PermissionListResponse(BaseModel):
    success: bool
    message: str
    total_permissions: int
    data: List[Permission]

class PermissionResponse(BaseModel):
    success: bool
    message: str
    data: Permission

class RolePermissionUpdate(BaseModel):
    permission_uuids: List[UUID4]

class RolePermissionDetail(BaseModel):
    permission: Permission
    is_given: bool

class RolePermissionListResponse(BaseModel):
    success: bool
    message: str
    data: List[RolePermissionDetail]
