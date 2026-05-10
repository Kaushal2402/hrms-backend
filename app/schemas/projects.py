from typing import Optional, List, Any
from pydantic import BaseModel, Field, ConfigDict
from datetime import datetime, date
from decimal import Decimal
import uuid

from app.models.projects import (
    ProjectType, ProjectStatus, ProjectPriority, BillingType,
    TaskStatus, TaskType, MemberRole, TimesheetPeriodType, PolicyApplicableTo
)
from app.schemas.employee import EmployeeSummarySchema


# ============================================================
# CLIENT SCHEMAS
# ============================================================

class ProjectClientBase(BaseModel):
    client_code: str = Field(..., max_length=50)
    client_name: str = Field(..., max_length=200)
    contact_person: Optional[str] = None
    contact_email: Optional[str] = None
    contact_phone: Optional[str] = None
    billing_currency: Optional[str] = "INR"
    default_billing_rate: Optional[Decimal] = None
    address: Optional[str] = None
    is_active: bool = True
    is_internal: bool = False

class ProjectClientCreate(ProjectClientBase):
    pass

class ProjectClientUpdate(BaseModel):
    client_name: Optional[str] = None
    contact_person: Optional[str] = None
    contact_email: Optional[str] = None
    contact_phone: Optional[str] = None
    billing_currency: Optional[str] = None
    default_billing_rate: Optional[Decimal] = None
    address: Optional[str] = None
    is_active: Optional[bool] = None
    is_internal: Optional[bool] = None

class ProjectClientSchema(ProjectClientBase):
    uuid: uuid.UUID
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)

class ProjectClientResponse(BaseModel):
    success: bool
    message: str
    data: Optional[ProjectClientSchema] = None

class ProjectClientListResponse(BaseModel):
    success: bool
    message: str
    data: List[ProjectClientSchema] = []
    pagination: Optional[Any] = None


# ============================================================
# PROJECT SCHEMAS
# ============================================================

class ProjectBase(BaseModel):
    project_code: str = Field(..., max_length=50)
    project_name: str = Field(..., max_length=200)
    description: Optional[str] = None
    project_type: ProjectType = ProjectType.BILLABLE
    status: ProjectStatus = ProjectStatus.PLANNING
    priority: Optional[ProjectPriority] = ProjectPriority.MEDIUM
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    budget_hours: Optional[Decimal] = None
    budget_amount: Optional[Decimal] = None
    billing_rate: Optional[Decimal] = None
    billing_type: Optional[BillingType] = BillingType.HOURLY
    color_code: Optional[str] = None
    tags: Optional[List[str]] = None
    is_active: bool = True

class ProjectCreate(ProjectBase):
    client_uuid: Optional[uuid.UUID] = None
    project_manager_uuid: Optional[uuid.UUID] = None
    department_uuid: Optional[uuid.UUID] = None

class ProjectUpdate(BaseModel):
    project_name: Optional[str] = None
    description: Optional[str] = None
    project_type: Optional[ProjectType] = None
    status: Optional[ProjectStatus] = None
    priority: Optional[ProjectPriority] = None
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    actual_end_date: Optional[date] = None
    budget_hours: Optional[Decimal] = None
    budget_amount: Optional[Decimal] = None
    billing_rate: Optional[Decimal] = None
    billing_type: Optional[BillingType] = None
    color_code: Optional[str] = None
    tags: Optional[List[str]] = None
    is_active: Optional[bool] = None
    client_uuid: Optional[uuid.UUID] = None
    project_manager_uuid: Optional[uuid.UUID] = None

class ProjectBudgetSummary(BaseModel):
    budget_hours: Optional[Decimal] = None
    consumed_hours: Optional[Decimal] = None
    billable_hours: Optional[Decimal] = None
    remaining_hours: Optional[Decimal] = None
    burn_percentage: Optional[float] = None

class ProjectSchema(ProjectBase):
    uuid: uuid.UUID
    client_uuid: Optional[uuid.UUID] = None
    project_manager_uuid: Optional[uuid.UUID] = None
    department_uuid: Optional[uuid.UUID] = None
    consumed_hours: Decimal = Decimal("0")
    actual_end_date: Optional[date] = None
    budget_summary: Optional[ProjectBudgetSummary] = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)

    @classmethod
    def model_validate(cls, obj, **kwargs):
        instance = super().model_validate(obj, **kwargs)
        # Populate UUIDs from relationships
        if hasattr(obj, "client") and obj.client:
            instance.client_uuid = obj.client.uuid
        if hasattr(obj, "project_manager") and obj.project_manager:
            instance.project_manager_uuid = obj.project_manager.uuid
        if hasattr(obj, "department") and obj.department:
            instance.department_uuid = obj.department.uuid
            
        # Compute budget burn-down
        if obj.budget_hours:
            instance.budget_summary = ProjectBudgetSummary(
                budget_hours=obj.budget_hours,
                consumed_hours=obj.consumed_hours or Decimal("0"),
                billable_hours=obj.billable_hours or Decimal("0"),
                remaining_hours=obj.remaining_hours,
                burn_percentage=obj.budget_burn_percentage
            )
        return instance

class ProjectDetailSchema(ProjectSchema):
    client: Optional[ProjectClientSchema] = None
    project_manager: Optional[EmployeeSummarySchema] = None

    model_config = ConfigDict(from_attributes=True)

class ProjectResponse(BaseModel):
    success: bool
    message: str
    data: Optional[ProjectDetailSchema] = None

class ProjectListResponse(BaseModel):
    success: bool
    message: str
    data: List[ProjectSchema] = []
    pagination: Optional[Any] = None

class ProjectEmployeeViewSchema(BaseModel):
    uuid: uuid.UUID
    project_code: str
    project_name: str
    description: Optional[str] = None
    project_type: ProjectType
    status: ProjectStatus
    priority: Optional[ProjectPriority] = None
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    color_code: Optional[str] = None
    tags: Optional[List[str]] = None
    client_name: Optional[str] = None
    project_manager_name: Optional[str] = None
    role: Optional[MemberRole] = None

    model_config = ConfigDict(from_attributes=True)

class ProjectEmployeeViewListResponse(BaseModel):
    success: bool
    message: str
    data: List[ProjectEmployeeViewSchema] = []
    pagination: Optional[Any] = None


# ============================================================
# PROJECT TASK SCHEMAS
# ============================================================

class ProjectTaskBase(BaseModel):
    task_name: str = Field(..., max_length=300)
    task_code: Optional[str] = None
    description: Optional[str] = None
    status: TaskStatus = TaskStatus.TODO
    priority: Optional[ProjectPriority] = ProjectPriority.MEDIUM
    task_type: Optional[TaskType] = TaskType.FEATURE
    estimated_hours: Optional[Decimal] = None
    start_date: Optional[date] = None
    due_date: Optional[date] = None
    is_billable: Optional[bool] = None
    tags: Optional[List[str]] = None

class ProjectTaskCreate(ProjectTaskBase):
    project_uuid: uuid.UUID
    assigned_to_uuid: Optional[uuid.UUID] = None
    parent_task_uuid: Optional[uuid.UUID] = None

class ProjectTaskUpdate(BaseModel):
    task_name: Optional[str] = None
    task_code: Optional[str] = None
    description: Optional[str] = None
    status: Optional[TaskStatus] = None
    priority: Optional[ProjectPriority] = None
    task_type: Optional[TaskType] = None
    estimated_hours: Optional[Decimal] = None
    start_date: Optional[date] = None
    due_date: Optional[date] = None
    is_billable: Optional[bool] = None
    tags: Optional[List[str]] = None
    assigned_to_uuid: Optional[uuid.UUID] = None

class ProjectTaskSchema(ProjectTaskBase):
    uuid: uuid.UUID
    project_uuid: uuid.UUID = Field(default=None)
    assigned_to_uuid: Optional[uuid.UUID] = None
    parent_task_uuid: Optional[uuid.UUID] = None
    logged_hours: Decimal = Decimal("0")
    billable_hours: Decimal = Decimal("0")
    completed_at: Optional[datetime] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)

    @classmethod
    def model_validate(cls, obj, **kwargs):
        instance = super().model_validate(obj, **kwargs)
        if hasattr(obj, "project") and obj.project:
            instance.project_uuid = obj.project.uuid
        if hasattr(obj, "assigned_to") and obj.assigned_to:
            instance.assigned_to_uuid = obj.assigned_to.uuid
        if hasattr(obj, "parent_task") and obj.parent_task:
            instance.parent_task_uuid = obj.parent_task.uuid
        return instance

class ProjectTaskDetailSchema(ProjectTaskSchema):
    project: Optional[ProjectSchema] = None
    assigned_to: Optional[EmployeeSummarySchema] = None

    model_config = ConfigDict(from_attributes=True)

class ProjectTaskResponse(BaseModel):
    success: bool
    message: str
    data: Optional[ProjectTaskDetailSchema] = None

class ProjectTaskListResponse(BaseModel):
    success: bool
    message: str
    data: List[ProjectTaskDetailSchema] = []
    pagination: Optional[Any] = None


# ============================================================
# PROJECT MEMBER SCHEMAS
# ============================================================

class ProjectMemberCreate(BaseModel):
    employee_uuid: uuid.UUID
    role: MemberRole = MemberRole.DEVELOPER
    billing_rate: Optional[Decimal] = None
    allocated_hours: Optional[Decimal] = None
    joined_at: Optional[date] = None

class ProjectMemberUpdate(BaseModel):
    role: Optional[MemberRole] = None
    billing_rate: Optional[Decimal] = None
    allocated_hours: Optional[Decimal] = None
    is_active: Optional[bool] = None
    left_at: Optional[date] = None

class ProjectMemberSchema(BaseModel):
    uuid: uuid.UUID
    project_uuid: uuid.UUID = Field(default=None)
    employee_uuid: uuid.UUID = Field(default=None)
    employee: Optional[EmployeeSummarySchema] = None
    role: MemberRole
    billing_rate: Optional[Decimal] = None
    allocated_hours: Optional[Decimal] = None
    logged_hours: Decimal = Decimal("0")
    joined_at: Optional[date] = None
    left_at: Optional[date] = None
    is_active: bool
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)

    @classmethod
    def model_validate(cls, obj, **kwargs):
        instance = super().model_validate(obj, **kwargs)
        if hasattr(obj, "project") and obj.project:
            instance.project_uuid = obj.project.uuid
        if hasattr(obj, "employee") and obj.employee:
            instance.employee_uuid = obj.employee.uuid
        return instance

class ProjectMemberResponse(BaseModel):
    success: bool
    message: str
    data: Optional[ProjectMemberSchema] = None

class ProjectMemberListResponse(BaseModel):
    success: bool
    message: str
    data: List[ProjectMemberSchema] = []


# ============================================================
# ACTIVITY TYPE SCHEMAS
# ============================================================

class ActivityTypeBase(BaseModel):
    activity_code: str = Field(..., max_length=50)
    activity_name: str = Field(..., max_length=150)
    description: Optional[str] = None
    is_billable_default: bool = True
    color_code: Optional[str] = None
    is_active: bool = True

class ActivityTypeCreate(ActivityTypeBase):
    pass

class ActivityTypeUpdate(BaseModel):
    activity_name: Optional[str] = None
    description: Optional[str] = None
    is_billable_default: Optional[bool] = None
    color_code: Optional[str] = None
    is_active: Optional[bool] = None

class ActivityTypeSchema(ActivityTypeBase):
    uuid: uuid.UUID
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)

class ActivityTypeResponse(BaseModel):
    success: bool
    message: str
    data: Optional[ActivityTypeSchema] = None

class ActivityTypeListResponse(BaseModel):
    success: bool
    message: str
    data: List[ActivityTypeSchema] = []


# ============================================================
# TIMESHEET POLICY SCHEMAS
# ============================================================

class TimesheetPolicyBase(BaseModel):
    policy_name: str = Field(..., max_length=150)
    description: Optional[str] = None
    period_type: TimesheetPeriodType = TimesheetPeriodType.WEEKLY
    submission_deadline_days: int = 3
    max_hours_per_day: Decimal = Decimal("24")
    min_hours_per_day: Decimal = Decimal("0")
    require_task_selection: bool = True
    require_activity_type: bool = False
    allow_future_entries: bool = False
    allow_backdated_days: int = 7
    auto_submit: bool = False
    applicable_to: PolicyApplicableTo = PolicyApplicableTo.ALL
    department_ids: Optional[List[int]] = None
    employee_type_ids: Optional[List[int]] = None
    is_active: bool = True
    is_default: bool = False
    effective_from: Optional[date] = None

class TimesheetPolicyCreate(TimesheetPolicyBase):
    pass

class TimesheetPolicyUpdate(BaseModel):
    policy_name: Optional[str] = None
    description: Optional[str] = None
    period_type: Optional[TimesheetPeriodType] = None
    submission_deadline_days: Optional[int] = None
    max_hours_per_day: Optional[Decimal] = None
    min_hours_per_day: Optional[Decimal] = None
    require_task_selection: Optional[bool] = None
    require_activity_type: Optional[bool] = None
    allow_future_entries: Optional[bool] = None
    allow_backdated_days: Optional[int] = None
    auto_submit: Optional[bool] = None
    applicable_to: Optional[PolicyApplicableTo] = None
    department_ids: Optional[List[int]] = None
    is_active: Optional[bool] = None
    is_default: Optional[bool] = None
    effective_from: Optional[date] = None

class TimesheetPolicySchema(TimesheetPolicyBase):
    uuid: uuid.UUID
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)

class TimesheetPolicyResponse(BaseModel):
    success: bool
    message: str
    data: Optional[TimesheetPolicySchema] = None

class TimesheetPolicyListResponse(BaseModel):
    success: bool
    message: str
    data: List[TimesheetPolicySchema] = []
