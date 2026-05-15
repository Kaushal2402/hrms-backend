from pydantic import BaseModel, UUID4
from typing import List, Optional, Any, Generic, TypeVar
from datetime import datetime
from app.schemas.department import PaginatedResponse

T = TypeVar("T")

class PayrollAuditLogSchema(BaseModel):
    uuid: UUID4
    action_type: str
    entity_type: str
    entity_id: int
    employee_id: Optional[int] = None
    before_state: Optional[dict] = None
    after_state: Optional[dict] = None
    changed_fields: Optional[dict] = None
    change_summary: Optional[str] = None
    performed_by: int
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None
    risk_level: Optional[str] = None
    performed_at: datetime

    class Config:
        from_attributes = True

class PayrollAuditLogListResponse(PaginatedResponse[List[PayrollAuditLogSchema]]):
    pass

class ComplianceViolationSchema(BaseModel):
    issue: str
    severity: str
    entity_type: str
    entity_id: int

    class Config:
        from_attributes = True