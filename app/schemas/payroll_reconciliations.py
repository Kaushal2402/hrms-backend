from typing import List, Optional, Any
from datetime import date, datetime
from decimal import Decimal
from pydantic import BaseModel, UUID4, Field
from app.schemas.department import PaginatedResponse
from app.models.payroll import PayrollStatus

class PayrollReconciliationBase(BaseModel):
    payroll_period_uuid: UUID4
    previous_period_uuid: Optional[UUID4] = None
    notes: Optional[str] = Field(None, max_length=500)

class PayrollReconciliationCreate(PayrollReconciliationBase):
    pass

class PayrollReconciliationSchema(BaseModel):
    uuid: UUID4
    reconciliation_number: str
    reconciliation_date: date
    current_period_gross: Decimal
    previous_period_gross: Optional[Decimal] = None
    gross_variance: Optional[Decimal] = None
    gross_variance_percentage: Optional[Decimal] = None
    current_period_net: Decimal
    previous_period_net: Optional[Decimal] = None
    net_variance: Optional[Decimal] = None
    net_variance_percentage: Optional[Decimal] = None
    current_employee_count: int
    previous_employee_count: Optional[int] = None
    new_joiners: int
    exits: int
    status: PayrollStatus
    notes: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True

class PayrollReconciliationResponse(BaseModel):
    success: bool
    message: str
    data: Optional[PayrollReconciliationSchema] = None

class PayrollReconciliationListResponse(PaginatedResponse[List[PayrollReconciliationSchema]]):
    pass

class PayrollReconciliationIssueSchema(BaseModel):
    uuid: UUID4
    issue_type: str
    issue_description: str
    severity: str
    status: str
    financial_impact: Optional[Decimal] = None
    resolution_notes: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True

class PayrollReconciliationIssueListResponse(PaginatedResponse[List[PayrollReconciliationIssueSchema]]):
    pass

class IssueResolveUpdate(BaseModel):
    resolution_notes: Optional[str] = Field(None, min_length=1)