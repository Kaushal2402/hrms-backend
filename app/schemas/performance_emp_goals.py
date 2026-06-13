import uuid
from typing import List, Optional, Any
from decimal import Decimal
from datetime import date, datetime
from pydantic import BaseModel, ConfigDict, Field
from app.models.performance import GoalStatus, GoalMeasurementType

class EmployeeGoalBase(BaseModel):
    title: str
    description: Optional[str] = None
    start_date: date
    end_date: date
    measurement_type: GoalMeasurementType
    target_value: Optional[Decimal] = None
    current_value: Optional[Decimal] = Decimal("0.00")
    baseline_value: Optional[Decimal] = None
    unit: Optional[str] = None
    weight: Optional[Decimal] = Decimal("100.00")
    status: Optional[GoalStatus] = GoalStatus.DRAFT
    progress_percentage: Optional[Decimal] = Decimal("0.00")
    is_stretch_goal: Optional[bool] = False
    tags: Optional[List[str]] = []
    
    # SMART fields
    is_specific: Optional[bool] = False
    is_measurable: Optional[bool] = False
    is_achievable: Optional[bool] = False
    is_relevant: Optional[bool] = False
    is_time_bound: Optional[bool] = False
    
    # OKR fields
    objective_key: Optional[str] = None
    is_key_result: Optional[bool] = False

class EmployeeGoalCreate(EmployeeGoalBase):
    employee_uuid: uuid.UUID
    framework_uuid: uuid.UUID
    parent_dept_goal_uuid: Optional[uuid.UUID] = None
    parent_org_goal_uuid: Optional[uuid.UUID] = None
    appraisal_cycle_uuid: Optional[uuid.UUID] = None
    parent_objective_uuid: Optional[uuid.UUID] = None

class EmployeeGoalUpdate(EmployeeGoalBase):
    title: Optional[str] = None
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    measurement_type: Optional[GoalMeasurementType] = None
    employee_uuid: Optional[uuid.UUID] = None
    framework_uuid: Optional[uuid.UUID] = None
    parent_dept_goal_uuid: Optional[uuid.UUID] = None
    parent_org_goal_uuid: Optional[uuid.UUID] = None
    appraisal_cycle_uuid: Optional[uuid.UUID] = None
    parent_objective_uuid: Optional[uuid.UUID] = None

class GoalApprovalRequest(BaseModel):
    approved: bool
    manager_comment: Optional[str] = None

class GoalStatusUpdateRequest(BaseModel):
    status: GoalStatus
    notes: Optional[str] = None

class EmployeeGoalSchema(EmployeeGoalBase):
    id: int
    uuid: uuid.UUID
    organization_id: int
    employee_id: int
    framework_id: int
    parent_dept_goal_id: Optional[int] = None
    parent_org_goal_id: Optional[int] = None
    appraisal_cycle_id: Optional[int] = None
    manager_id: Optional[int] = None
    approved_by: Optional[int] = None
    approved_at: Optional[datetime] = None
    manager_comment: Optional[str] = None
    
    # Relationships mapping (simplified)
    employee_name: Optional[str] = None
    manager_name: Optional[str] = None
    framework_name: Optional[str] = None
    approver_name: Optional[str] = None
    parent_dept_goal_title: Optional[str] = None
    parent_org_goal_title: Optional[str] = None
    
    # UUIDs for frontend editing
    employee_uuid: Optional[uuid.UUID] = None
    framework_uuid: Optional[uuid.UUID] = None
    parent_dept_goal_uuid: Optional[uuid.UUID] = None
    parent_org_goal_uuid: Optional[uuid.UUID] = None
    appraisal_cycle_uuid: Optional[uuid.UUID] = None
    parent_objective_uuid: Optional[uuid.UUID] = None

    model_config = ConfigDict(from_attributes=True, validation_alias=True)

class Pagination(BaseModel):
    total_records: int
    current_page: int
    total_pages: int
    page_size: int

class EmployeeGoalListResponse(BaseModel):
    success: bool
    message: str
    data: List[EmployeeGoalSchema]
    pagination: Pagination

class EmployeeGoalResponse(BaseModel):
    success: bool
    message: str
    data: EmployeeGoalSchema

class MyGoalsGroup(BaseModel):
    framework_id: uuid.UUID
    framework_name: str
    overall_progress: float
    goals: List[EmployeeGoalSchema]

class MyGoalsDashboardResponse(BaseModel):
    groups: List[MyGoalsGroup]
    overall_completion_percentage: float

class GoalProgressBase(BaseModel):
    check_in_date: date
    current_value: Optional[Decimal] = None
    progress_percentage: Decimal
    status: GoalStatus
    update_notes: Optional[str] = None
    blockers: Optional[str] = None
    next_steps: Optional[str] = None
    attachments: Optional[List[dict]] = []

class GoalProgressCreate(GoalProgressBase):
    pass

class GoalProgressUpdate(BaseModel):
    check_in_date: Optional[date] = None
    current_value: Optional[Decimal] = None
    progress_percentage: Optional[Decimal] = None
    status: Optional[GoalStatus] = None
    update_notes: Optional[str] = None
    blockers: Optional[str] = None
    next_steps: Optional[str] = None
    attachments: Optional[List[dict]] = None

class GoalProgressAcknowledge(BaseModel):
    manager_comment: Optional[str] = None

class GoalProgressSchema(GoalProgressBase):
    id: int
    uuid: uuid.UUID
    employee_goal_id: int
    employee_id: int
    acknowledged_by: Optional[int] = None
    acknowledged_at: Optional[datetime] = None
    manager_comment: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True, validation_alias=True)

class GoalProgressResponse(BaseModel):
    success: bool
    message: str
    data: GoalProgressSchema

class GoalProgressListResponse(BaseModel):
    success: bool
    message: str
    data: List[GoalProgressSchema]
    pagination: Pagination

class EmployeeGoalLookupSchema(BaseModel):
    uuid: uuid.UUID
    title: str
    status: GoalStatus
    employee_name: Optional[str] = None
    employee_uuid: Optional[uuid.UUID] = None
    progress_percentage: Optional[Decimal] = Decimal("0.00")

    model_config = ConfigDict(from_attributes=True, validation_alias=True)

class EmployeeGoalLookupResponse(BaseModel):
    success: bool
    message: str
    data: List[EmployeeGoalLookupSchema]
    pagination: Pagination

