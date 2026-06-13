from pydantic import BaseModel, ConfigDict
from typing import Optional, List
from datetime import datetime
from decimal import Decimal
import uuid
from app.models.performance import GoalType, GoalStatus

class GoalAlignmentBase(BaseModel):
    parent_goal_type: GoalType
    parent_goal_uuid: uuid.UUID
    child_goal_type: GoalType
    child_goal_uuid: uuid.UUID
    alignment_weight: Decimal = Decimal('100.00')
    notes: Optional[str] = None

class GoalAlignmentCreate(GoalAlignmentBase):
    pass

class GoalAlignmentUpdate(BaseModel):
    alignment_weight: Optional[Decimal] = None
    notes: Optional[str] = None

class GoalAlignmentSchema(GoalAlignmentBase):
    id: int
    organization_id: int
    created_by: int
    created_at: datetime
    parent_goal_title: Optional[str] = None
    child_goal_title: Optional[str] = None

    model_config = ConfigDict(from_attributes=True, validation_alias=True)

class GoalAlignmentResponse(BaseModel):
    success: bool
    message: str
    data: GoalAlignmentSchema

class PaginationSchema(BaseModel):
    current_page: int
    total_pages: int
    total_records: int
    limit: int

class GoalAlignmentListResponse(BaseModel):
    success: bool
    message: str
    data: List[GoalAlignmentSchema]
    pagination: Optional[PaginationSchema] = None

class GoalTreeNode(BaseModel):
    goal_id: int
    goal_uuid: uuid.UUID
    goal_type: GoalType
    title: str
    progress_percentage: Decimal
    status: GoalStatus
    employee_name: Optional[str] = None
    department_name: Optional[str] = None
    children: List['GoalTreeNode'] = []

    model_config = ConfigDict(from_attributes=True)

class GoalTreeResponse(BaseModel):
    success: bool
    message: str
    data: List[GoalTreeNode]

GoalTreeNode.model_rebuild()
