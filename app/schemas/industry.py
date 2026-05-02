from typing import Optional, List
from pydantic import BaseModel, UUID4, constr
from datetime import datetime

class IndustryBase(BaseModel):
    name: constr(min_length=1, max_length=100)
    description: Optional[str] = None
    icon: Optional[str] = None
    is_active: Optional[bool] = True

class IndustryCreate(IndustryBase):
    pass

class IndustryUpdate(BaseModel):
    name: Optional[constr(min_length=1, max_length=100)] = None
    description: Optional[str] = None
    icon: Optional[str] = None
    is_active: Optional[bool] = None

class IndustrySchema(IndustryBase):
    uuid: UUID4
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

class IndustryListResponse(BaseModel):
    success: bool
    message: str
    data: List[IndustrySchema]

class IndustryResponse(BaseModel):
    success: bool
    message: str
    data: IndustrySchema
