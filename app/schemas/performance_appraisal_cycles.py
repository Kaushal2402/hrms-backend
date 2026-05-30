from pydantic import BaseModel, UUID4, Field, model_validator, field_validator
from typing import List, Optional, Any, Generic, TypeVar
from datetime import date, datetime
from decimal import Decimal
from app.models.performance import CycleFrequency, CycleStatus
from app.schemas.department import PaginatedResponse

T = TypeVar("T")

class AppraisalCycleBase(BaseModel):
    name: str
    frequency: CycleFrequency
    fiscal_year: Optional[str] = None
    review_period_start: date
    review_period_end: date
    goal_setting_start: Optional[date] = None
    goal_setting_end: Optional[date] = None
    self_appraisal_start: date
    self_appraisal_end: date
    manager_review_start: date
    manager_review_end: date
    calibration_start: Optional[date] = None
    calibration_end: Optional[date] = None
    result_publication_date: Optional[date] = None
    template_id: int
    rating_scale_id: int
    include_probationary: bool = False
    minimum_tenure_days: int = 90
    applicable_departments: List[int] = []
    applicable_employee_types: List[str] = []
    require_self_appraisal: bool = True
    require_360_feedback: bool = False
    require_calibration: bool = False
    allow_employee_acknowledgment: bool = True
    bell_curve_enabled: bool = False
    bell_curve_config: Optional[dict] = None
    reminders_enabled: bool = True
    reminder_days_before: List[int] = [7, 3, 1]

    class Config:
        from_attributes = True

class AppraisalCycleCreate(AppraisalCycleBase):
    pass

class AppraisalCycleUpdate(BaseModel):
    name: Optional[str] = None
    frequency: Optional[CycleFrequency] = None
    fiscal_year: Optional[str] = None
    review_period_start: Optional[date] = None
    review_period_end: Optional[date] = None
    self_appraisal_start: Optional[date] = None
    self_appraisal_end: Optional[date] = None
    manager_review_start: Optional[date] = None
    manager_review_end: Optional[date] = None
    status: Optional[CycleStatus] = None

class AppraisalCycleSchema(AppraisalCycleBase):
    uuid: UUID4
    status: CycleStatus
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

class AppraisalCycleResponse(BaseModel):
    success: bool
    message: str
    data: Optional[AppraisalCycleSchema] = None

class AppraisalCycleListResponse(PaginatedResponse[List[AppraisalCycleSchema]]):
    pass

class CycleLaunchResponse(BaseModel):
    success: bool
    message: str
    data: dict

class CycleDashboardResponse(BaseModel):
    success: bool
    message: str
    data: dict