from pydantic import BaseModel, UUID4
from typing import List, Optional, Union, Dict, Any
from datetime import datetime, date
from decimal import Decimal
from app.models.performance import GoalStatus, GoalMeasurementType
from app.schemas.department import PaginatedResponse
from app.schemas.performance_appraisals import EmployeePerformanceSummary
from app.schemas.performance_goal_frameworks import GoalFrameworkSchema
from app.schemas.performance_org_goals import OrgGoalSchema

class DeptGoalBase(BaseModel):
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
    tags: Optional[List[str]] = []

    class Config:
        from_attributes = True

class DeptGoalCreate(DeptGoalBase):
    department_id: Union[int, UUID4, str]
    framework_id: Union[int, UUID4, str]
    owner_id: Union[int, UUID4, str]
    parent_org_goal_id: Optional[Union[int, UUID4, str]] = None

class DeptGoalUpdate(BaseModel):
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
    tags: Optional[List[str]] = None
    department_id: Optional[Union[int, UUID4, str]] = None
    framework_id: Optional[Union[int, UUID4, str]] = None
    owner_id: Optional[Union[int, UUID4, str]] = None
    parent_org_goal_id: Optional[Union[int, UUID4, str]] = None

    class Config:
        from_attributes = True

class DeptGoalStatusUpdate(BaseModel):
    status: GoalStatus
    notes: Optional[str] = None

class DepartmentBasicSchema(BaseModel):
    uuid: UUID4
    name: str

    class Config:
        from_attributes = True

class DeptGoalSchema(DeptGoalBase):
    uuid: UUID4
    progress_percentage: Optional[Decimal] = Decimal("0.00")
    owner: Optional[EmployeePerformanceSummary] = None
    framework: Optional[GoalFrameworkSchema] = None
    parent_org_goal: Optional[OrgGoalSchema] = None
    department: Optional[DepartmentBasicSchema] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

class DeptGoalResponse(BaseModel):
    success: bool
    message: str
    data: Optional[DeptGoalSchema] = None

class DeptGoalListResponse(PaginatedResponse[List[DeptGoalSchema]]):
    pass
