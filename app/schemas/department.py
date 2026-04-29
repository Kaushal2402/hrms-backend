import uuid
from pydantic import BaseModel, UUID4, field_validator, Field
from typing import Optional, List, Generic, TypeVar, Union, Any
from datetime import datetime

T = TypeVar('T')

class PaginationData(BaseModel):
    total_records: int
    current_page: int
    total_pages: int
    page_size: Optional[int] = None

class PaginatedResponse(BaseModel, Generic[T]):
    success: bool
    message: Optional[str] = None
    data: Optional[T] = None
    pagination: Optional[PaginationData] = None

# Department Schemas
class DepartmentBase(BaseModel):
    department_code: str = Field(..., max_length=50)
    department_name: str = Field(..., max_length=150)
    description: Optional[str] = None
    is_active: Optional[bool] = True

    @field_validator('department_name')
    def name_must_not_be_empty(cls, v):
        if not v or not v.strip():
            raise ValueError('Department name must not be empty')
        return v

class DepartmentCreate(DepartmentBase):
    parent_department_uuid: Optional[UUID4] = None
    head_of_department_uuid: Optional[UUID4] = None

class DepartmentUpdate(BaseModel):
    department_code: Optional[str] = Field(None, max_length=50)
    department_name: Optional[str] = Field(None, max_length=150)
    description: Optional[str] = None
    is_active: Optional[bool] = None
    parent_department_uuid: Optional[UUID4] = None
    head_of_department_uuid: Optional[UUID4] = None

class DepartmentSchema(DepartmentBase):
    uuid: UUID4
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    
    # These will be populated manually or via custom validators if from_attributes=True
    parent_department_uuid: Optional[UUID4] = None
    head_of_department_uuid: Optional[UUID4] = None
    
    # We will need to map these in the endpoint or use a property on the model
    # For now, let's assume we map them in the route handler or using a validator here.
    
    class Config:
        from_attributes = True

    @field_validator('parent_department_uuid', mode='before', check_fields=False)
    @classmethod
    def get_parent_uuid(cls, v, info):
        # If v is already UUID, return it
        if isinstance(v, uuid.UUID):
            return v
        # If we are parsing from an ORM object (parent_department loading)
        # We can't easily access the parent object here if 'v' is just the value of the field?
        # But the field on the model is 'parent_department_id'. There is no 'parent_department_uuid' on the model.
        # So we must access the relationship 'parent_department'.
        # This requires `validation_alias` or similar? or simply passing the whole object?
        return v

    # Actually, simpler way: define them as properties on the ORM model to return UUID,
    # OR map them in the endpoint before creating schema.
    # Given the complexity, I will remove `DepartmentInDBBase` inheritance chain confusion.
    # I'll just keep the schema clean.
    pass

class DepartmentDetailSchema(DepartmentSchema):
    employee_count: int = 0

class DepartmentResponse(PaginatedResponse[DepartmentSchema]):
    pass

class DepartmentDetailResponse(PaginatedResponse[DepartmentDetailSchema]):
    pass

class DepartmentListResponse(PaginatedResponse[List[DepartmentSchema]]):
    pass

class DepartmentHierarchySchema(DepartmentSchema):
    sub_departments: List['DepartmentHierarchySchema'] = []

class DepartmentHierarchyListResponse(PaginatedResponse[List[DepartmentHierarchySchema]]):
    pass

class DepartmentDeleteResponse(PaginatedResponse[None]):
    pass

# Correct forward refs
DepartmentHierarchySchema.model_rebuild()
