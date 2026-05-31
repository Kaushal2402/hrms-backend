from pydantic import BaseModel, UUID4
from typing import List, Optional, Union, Dict, Any
from datetime import datetime, date
from decimal import Decimal
from app.models.performance import GoalFrameworkType, GoalStatus, GoalMeasurementType
from app.schemas.department import PaginatedResponse
from app.schemas.performance_appraisals import EmployeePerformanceSummary
from app.schemas.performance_goal_frameworks import GoalFrameworkSchema

class OrgGoalBase(BaseModel):
    title: str
    description: Optional[str] = None
    start_date: date
    end_date: date
    fiscal_year: Optional[str] = None
    measurement_type: GoalMeasurementType
    target_value: Optional[Decimal] = None
    current_value: Optional[Decimal] = Decimal("0.00")
    unit: Optional[str] = None
    status: Optional[GoalStatus] = GoalStatus.DRAFT
    weight: Optional[Decimal] = Decimal("100.00")
    is_public: Optional[bool] = True
    tags: Optional[List[str]] = []
    attachments: Optional[List[Any]] = []

    class Config:
        from_attributes = True

class OrgGoalCreate(OrgGoalBase):
    framework_id: Union[int, UUID4, str]
    owner_id: Union[int, UUID4, str]

class OrgGoalUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    fiscal_year: Optional[str] = None
    measurement_type: Optional[GoalMeasurementType] = None
    target_value: Optional[Decimal] = None
    current_value: Optional[Decimal] = None
    unit: Optional[str] = None
    status: Optional[GoalStatus] = None
    weight: Optional[Decimal] = None
    progress_percentage: Optional[Decimal] = None
    is_public: Optional[bool] = None
    tags: Optional[List[str]] = None
    attachments: Optional[List[Any]] = None
    framework_id: Optional[Union[int, UUID4, str]] = None
    owner_id: Optional[Union[int, UUID4, str]] = None

    class Config:
        from_attributes = True

class OrgGoalStatusUpdate(BaseModel):
    status: GoalStatus
    notes: Optional[str] = None

class OrgGoalSchema(OrgGoalBase):
    uuid: UUID4
    goal_type: Optional[str] = None
    progress_percentage: Optional[Decimal] = Decimal("0.00")
    status_notes: Optional[str] = None
    owner: Optional[EmployeePerformanceSummary] = None
    framework: Optional[GoalFrameworkSchema] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

class OrgGoalResponse(BaseModel):
    success: bool
    message: str
    data: Optional[OrgGoalSchema] = None

class OrgGoalListResponse(PaginatedResponse[List[OrgGoalSchema]]):
    pass

class GoalCascadeItem(BaseModel):
    uuid: UUID4
    title: str
    goal_type: str  # "ORGANIZATION", "DEPARTMENT", "INDIVIDUAL"
    status: GoalStatus
    progress_percentage: Decimal
    owner_name: str
    children: List["GoalCascadeItem"] = []

    class Config:
        from_attributes = True

# Resolve self-referencing forward reference in GoalCascadeItem
GoalCascadeItem.model_rebuild()

class GoalCascadeResponse(BaseModel):
    success: bool
    message: str
    data: GoalCascadeItem

class OrgGoalSummarySchema(BaseModel):
    total: int
    on_track: int
    on_track_percentage: float
    at_risk: int
    at_risk_percentage: float
    behind: int
    behind_percentage: float
    completed: int
    completed_percentage: float
    average_progress: float = 0.0

    class Config:
        from_attributes = True

class OrgGoalSummaryResponse(BaseModel):
    success: bool
    message: str
    data: OrgGoalSummarySchema
