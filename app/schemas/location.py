from pydantic import BaseModel, UUID4, field_validator, Field
from typing import Optional, List, Generic, TypeVar
from datetime import datetime
from app.schemas.department import PaginatedResponse, PaginationData

class LocationBase(BaseModel):
    location_code: str = Field(..., max_length=50)
    location_name: str = Field(..., max_length=150)
    location_type: Optional[str] = Field(None, max_length=50)
    
    address_line1: Optional[str] = Field(None, max_length=255)
    address_line2: Optional[str] = Field(None, max_length=255)
    city: Optional[str] = Field(None, max_length=100)
    state: Optional[str] = Field(None, max_length=100)
    country: str = Field(..., max_length=100)
    pincode: Optional[str] = Field(None, max_length=20)
    
    phone: Optional[str] = Field(None, max_length=20)
    email: Optional[str] = Field(None, max_length=255)
    time_zone: Optional[str] = Field(None, max_length=50)
    
    is_active: Optional[bool] = True

    @field_validator('location_code', 'location_name', 'country')
    def check_not_empty(cls, v):
        if not v or not v.strip():
            raise ValueError('Field must not be empty')
        return v

class LocationCreate(LocationBase):
    pass

class LocationUpdate(BaseModel):
    location_code: Optional[str] = Field(None, max_length=50)
    location_name: Optional[str] = Field(None, max_length=150)
    location_type: Optional[str] = Field(None, max_length=50)
    
    address_line1: Optional[str] = Field(None, max_length=255)
    address_line2: Optional[str] = Field(None, max_length=255)
    city: Optional[str] = Field(None, max_length=100)
    state: Optional[str] = Field(None, max_length=100)
    country: Optional[str] = Field(None, max_length=100)
    pincode: Optional[str] = Field(None, max_length=20)
    
    phone: Optional[str] = Field(None, max_length=20)
    email: Optional[str] = Field(None, max_length=255)
    time_zone: Optional[str] = Field(None, max_length=50)
    
    is_active: Optional[bool] = None

    @field_validator('location_code', 'location_name', 'country')
    def check_not_empty(cls, v):
        if v is not None and (not v or not v.strip()):
            raise ValueError('Field must not be empty')
        return v

class LocationSchema(LocationBase):
    uuid: UUID4
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    
    class Config:
        from_attributes = True

class LocationResponse(PaginatedResponse[LocationSchema]):
    pass

class LocationListResponse(PaginatedResponse[List[LocationSchema]]):
    pass

class LocationDetailSchema(LocationSchema):
    employee_count: int = 0

class LocationDetailResponse(PaginatedResponse[LocationDetailSchema]):
    pass

class LocationDeleteResponse(PaginatedResponse[None]):
    pass
