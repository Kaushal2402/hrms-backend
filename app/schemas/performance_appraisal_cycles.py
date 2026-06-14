from pydantic import BaseModel, UUID4, Field, model_validator, field_validator
from typing import List, Optional, Any, Generic, TypeVar, Union
from datetime import date, datetime
from decimal import Decimal
from app.models.performance import CycleFrequency, CycleStatus
from app.schemas.department import PaginatedResponse
from app.schemas.performance_appraisals import AppraisalTemplateSummary, RatingScaleSummary

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
    include_probationary: bool = False
    minimum_tenure_days: int = 90
    applicable_departments: List[UUID4] = []
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
    template_uuid: UUID4
    rating_scale_uuid: UUID4

class AppraisalCycleUpdate(BaseModel):
    name: Optional[str] = None
    frequency: Optional[CycleFrequency] = None
    fiscal_year: Optional[str] = None
    review_period_start: Optional[date] = None
    review_period_end: Optional[date] = None
    goal_setting_start: Optional[date] = None
    goal_setting_end: Optional[date] = None
    self_appraisal_start: Optional[date] = None
    self_appraisal_end: Optional[date] = None
    manager_review_start: Optional[date] = None
    manager_review_end: Optional[date] = None
    calibration_start: Optional[date] = None
    calibration_end: Optional[date] = None
    result_publication_date: Optional[date] = None
    template_uuid: Optional[UUID4] = None
    rating_scale_uuid: Optional[UUID4] = None
    include_probationary: Optional[bool] = None
    minimum_tenure_days: Optional[int] = None
    applicable_departments: Optional[List[UUID4]] = None
    applicable_employee_types: Optional[List[str]] = None
    require_self_appraisal: Optional[bool] = None
    require_360_feedback: Optional[bool] = None
    require_calibration: Optional[bool] = None
    allow_employee_acknowledgment: Optional[bool] = None
    bell_curve_enabled: Optional[bool] = None
    bell_curve_config: Optional[dict] = None
    reminders_enabled: Optional[bool] = None
    reminder_days_before: Optional[List[int]] = None
    status: Optional[CycleStatus] = None

class AppraisalCycleSchema(AppraisalCycleBase):
    uuid: UUID4
    status: CycleStatus
    template_uuid: UUID4
    rating_scale_uuid: UUID4
    advance_history: Optional[List[dict]] = []
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

class AppraisalCycleResponse(BaseModel):
    success: bool
    message: str
    data: Optional[AppraisalCycleSchema] = None

class DepartmentSummarySchema(BaseModel):
    uuid: UUID4
    department_name: str
    department_code: str

    class Config:
        from_attributes = True

class AppraisalCycleDetailSchema(AppraisalCycleSchema):
    template: Optional[AppraisalTemplateSummary] = None
    rating_scale: Optional[RatingScaleSummary] = None
    departments: Optional[List[DepartmentSummarySchema]] = None

    class Config:
        from_attributes = True

class AppraisalCycleDetailResponse(BaseModel):
    success: bool
    message: str
    data: Optional[AppraisalCycleDetailSchema] = None

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

class AppraisalCycleLookupSchema(BaseModel):
    uuid: UUID4
    name: str
    status: CycleStatus
    frequency: CycleFrequency

    class Config:
        from_attributes = True

class AppraisalCycleLookupResponse(BaseModel):
    success: bool
    message: str
    data: List[AppraisalCycleLookupSchema]

# ── Action schemas ─────────────────────────────────────────────────

class CycleLaunchRequest(BaseModel):
    """No body required — launch is fully driven by cycle configuration."""
    pass

class CycleAdvancePhaseRequest(BaseModel):
    force_advance: bool = False
    notes: Optional[str] = None

class CyclePublishResultsRequest(BaseModel):
    publish_all: bool = True
    employee_uuids: Optional[List[UUID4]] = None  # selective publish when publish_all=False

class PendingEmployeeItem(BaseModel):
    uuid: UUID4
    full_name: str
    department: Optional[str] = None
    appraisal_status: str
    manager_name: Optional[str] = None
    manager_uuid: Optional[UUID4] = None

class PendingListResponse(PaginatedResponse[List[PendingEmployeeItem]]):
    pass

class CycleDashboardData(BaseModel):
    total_employees: int
    not_started_count: int
    self_in_progress_count: int
    self_submitted_count: int
    manager_in_progress_count: int
    manager_reviewed_count: int
    calibrated_count: int
    published_count: int
    acknowledged_count: int
    completion_percentage: float
    pending_list: List[PendingEmployeeItem]

from enum import Enum

class RecipientGroup(str, Enum):
    EMPLOYEES = "employees"
    MANAGERS = "managers"
    ALL = "all"

class SendRemindersRequest(BaseModel):
    phase: CycleStatus
    recipient_group: RecipientGroup
    department_uuids: Optional[List[UUID4]] = None
    custom_message: Optional[str] = None

class SendRemindersResponse(BaseModel):
    success: bool
    message: str
    data: dict