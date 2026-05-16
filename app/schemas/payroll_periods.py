from typing import List, Optional, Generic, TypeVar
from pydantic import BaseModel, UUID4, Field
from datetime import date, datetime
from decimal import Decimal
from app.models.payroll import PayFrequency, PayrollStatus

T = TypeVar('T')

class PaginatedResponse(BaseModel, Generic[T]):
    success: bool
    message: str
    data: T
    pagination: dict

class PayrollPeriodBase(BaseModel):
    period_name: str
    period_code: str
    period_start_date: date
    period_end_date: date
    payment_date: date
    pay_frequency: PayFrequency
    total_working_days: int
    financial_year: str
    notes: Optional[str] = None

class PayrollPeriodCreate(PayrollPeriodBase):
    pass

class PayrollPeriodUpdate(BaseModel):
    period_name: Optional[str] = None
    period_code: Optional[str] = None
    period_start_date: Optional[date] = None
    period_end_date: Optional[date] = None
    payment_date: Optional[date] = None
    total_working_days: Optional[int] = None
    notes: Optional[str] = None

class PayrollPeriodSchema(PayrollPeriodBase):
    uuid: UUID4
    status: PayrollStatus
    is_locked: bool
    total_employees: int
    total_gross_amount: Decimal
    total_deductions: Decimal
    total_net_amount: Decimal
    total_employer_contributions: Decimal
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

class PayrollPeriodResponse(BaseModel):
    success: bool
    message: str
    data: Optional[PayrollPeriodSchema] = None

class PayrollPeriodListResponse(PaginatedResponse[List[PayrollPeriodSchema]]):
    pass

class PayrollPeriodAction(BaseModel):
    comments: Optional[str] = None
    reason: Optional[str] = None

class PayrollSummaryResponse(BaseModel):
    success: bool
    message: str
    data: dict