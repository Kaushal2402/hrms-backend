from pydantic import BaseModel, UUID4, Field, model_validator
from typing import List, Optional, Generic, TypeVar
from datetime import datetime
from app.models.performance import GoalFrameworkType
from app.schemas.department import PaginatedResponse

T = TypeVar("T")

class GoalFrameworkBase(BaseModel):
    name: str
    framework_type: GoalFrameworkType
    description: Optional[str] = None
    max_objectives_per_employee: int = 5
    max_key_results_per_objective: int = 5
    require_specific: bool = True
    require_measurable: bool = True
    require_time_bound: bool = True
    goal_weight_enabled: bool = True
    default_scoring_method: str = "weighted_average"
    is_active: bool = True

class GoalFrameworkCreate(GoalFrameworkBase):
    pass

class GoalFrameworkUpdate(BaseModel):
    name: Optional[str] = None
    framework_type: Optional[GoalFrameworkType] = None
    description: Optional[str] = None
    max_objectives_per_employee: Optional[int] = None
    max_key_results_per_objective: Optional[int] = None
    require_specific: Optional[bool] = None
    require_measurable: Optional[bool] = None
    require_time_bound: Optional[bool] = None
    goal_weight_enabled: Optional[bool] = None
    default_scoring_method: Optional[str] = None
    is_active: Optional[bool] = None

class GoalFrameworkSchema(GoalFrameworkBase):
    uuid: UUID4
    is_default: bool
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

class GoalFrameworkResponse(BaseModel):
    success: bool
    message: str
    data: Optional[GoalFrameworkSchema] = None

class GoalFrameworkListResponse(PaginatedResponse[List[GoalFrameworkSchema]]):
    pass