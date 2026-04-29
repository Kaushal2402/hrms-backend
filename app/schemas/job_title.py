from pydantic import BaseModel, UUID4, field_validator, Field
from typing import Optional, List
from datetime import datetime
from app.schemas.department import PaginatedResponse

class JobTitleBase(BaseModel):
    title_code: str = Field(..., max_length=50)
    title_name: str = Field(..., max_length=150)
    job_level: Optional[str] = Field(None, max_length=50)
    job_family: Optional[str] = Field(None, max_length=100)
    description: Optional[str] = None
    responsibilities: Optional[str] = None
    qualifications: Optional[str] = None
    is_active: Optional[bool] = True

    @field_validator('title_code', 'title_name')
    def check_not_empty(cls, v):
        if not v or not v.strip():
            raise ValueError('Field must not be empty')
        return v

class JobTitleCreate(JobTitleBase):
    pass

class JobTitleUpdate(BaseModel):
    title_code: Optional[str] = Field(None, max_length=50)
    title_name: Optional[str] = Field(None, max_length=150)
    job_level: Optional[str] = Field(None, max_length=50)
    job_family: Optional[str] = Field(None, max_length=100)
    description: Optional[str] = None
    responsibilities: Optional[str] = None
    qualifications: Optional[str] = None
    is_active: Optional[bool] = None

    @field_validator('title_code', 'title_name')
    def check_not_empty(cls, v):
        if v is not None and (not v or not v.strip()):
            raise ValueError('Field must not be empty')
        return v

class JobTitleSchema(JobTitleBase):
    uuid: UUID4
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    
    class Config:
        from_attributes = True

class JobTitleResponse(PaginatedResponse[JobTitleSchema]):
    pass

class JobTitleListResponse(PaginatedResponse[List[JobTitleSchema]]):
    pass

class JobTitleDetailSchema(JobTitleSchema):
    employee_count: int = 0

class JobTitleDetailResponse(PaginatedResponse[JobTitleDetailSchema]):
    pass

class JobTitleDeleteResponse(PaginatedResponse[None]):
    pass
