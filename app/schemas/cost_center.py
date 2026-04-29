from pydantic import BaseModel, UUID4, field_validator
from typing import Optional, List
from datetime import datetime
from app.schemas.department import PaginatedResponse

class CostCenterBase(BaseModel):
    cost_center_code: str
    cost_center_name: str
    description: Optional[str] = None
    is_active: Optional[bool] = True

    @field_validator('cost_center_code', 'cost_center_name')
    def check_not_empty(cls, v):
        if not v or not v.strip():
            raise ValueError('Field must not be empty')
        return v

class CostCenterCreate(CostCenterBase):
    pass

class CostCenterUpdate(BaseModel):
    cost_center_code: Optional[str] = None
    cost_center_name: Optional[str] = None
    description: Optional[str] = None
    is_active: Optional[bool] = None

    @field_validator('cost_center_code', 'cost_center_name')
    def check_not_empty(cls, v):
        if v is not None and (not v or not v.strip()):
            raise ValueError('Field must not be empty')
        return v

class CostCenterSchema(CostCenterBase):
    uuid: UUID4
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    
    class Config:
        from_attributes = True

class CostCenterResponse(PaginatedResponse[CostCenterSchema]):
    pass

class CostCenterListResponse(PaginatedResponse[List[CostCenterSchema]]):
    pass

class CostCenterDetailSchema(CostCenterSchema):
    employee_count: int = 0

class CostCenterDetailResponse(PaginatedResponse[CostCenterDetailSchema]):
    pass

class CostCenterDeleteResponse(PaginatedResponse[None]):
    pass
