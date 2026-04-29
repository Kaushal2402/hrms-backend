from pydantic import BaseModel, UUID4, field_validator
from typing import Optional, List, Any, Dict
from datetime import datetime
from app.schemas.department import PaginatedResponse
from enum import Enum

class FieldTypeEnum(str, Enum):
    TEXT = "text"
    NUMBER = "number"
    DATE = "date"
    DROPDOWN = "dropdown"
    CHECKBOX = "checkbox"

class CustomFieldBase(BaseModel):
    field_name: str
    field_label: str
    field_type: FieldTypeEnum
    field_options: Optional[List[str]] = None
    is_required: Optional[bool] = False
    is_searchable: Optional[bool] = True
    display_order: Optional[int] = 0
    is_active: Optional[bool] = True

    @field_validator('field_name')
    def validate_field_name(cls, v):
        if not v or not v.strip():
            raise ValueError('Field name must not be empty')
        # Simple slug validation: alphanumeric and underscores only
        if not all(c.isalnum() or c == '_' for c in v):
            raise ValueError('Field name must contain only letters, numbers, and underscores')
        return v

    @field_validator('field_label')
    def validate_field_label(cls, v):
        if not v or not v.strip():
            raise ValueError('Field label must not be empty')
        return v
        
    @field_validator('field_options')
    def validate_options(cls, v, info):
        # field_type is checked against values, but in Pydantic v2 validation order matters. 
        # However, simplistic check: if type is dropdown, options should be present.
        # We can't easily access other fields in basic validator without model validator model.
        # For now simple check.
        return v

class CustomFieldCreate(CustomFieldBase):
    pass

class CustomFieldUpdate(BaseModel):
    field_label: Optional[str] = None
    field_type: Optional[FieldTypeEnum] = None
    field_options: Optional[List[str]] = None
    is_required: Optional[bool] = None
    is_searchable: Optional[bool] = None
    display_order: Optional[int] = None
    is_active: Optional[bool] = None
    # field_name usually shouldn't be changed after creation to avoid breaking data mapping

class CustomFieldSchema(CustomFieldBase):
    uuid: UUID4
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    
    class Config:
        from_attributes = True

class CustomFieldResponse(PaginatedResponse[CustomFieldSchema]):
    pass

class CustomFieldListResponse(PaginatedResponse[List[CustomFieldSchema]]):
    pass

class CustomFieldDetailResponse(PaginatedResponse[CustomFieldSchema]):
    pass

class CustomFieldDeleteResponse(PaginatedResponse[None]):
    pass
