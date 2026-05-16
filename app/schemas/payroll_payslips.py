from pydantic import BaseModel, UUID4, Field
from typing import List, Optional, Generic, TypeVar
from datetime import datetime, date
from decimal import Decimal
from app.models.payroll import PayslipStatus

T = TypeVar("T")

class PaginatedResponse(BaseModel, Generic[T]):
    success: bool
    message: str
    data: T
    pagination: dict

class PayslipBase(BaseModel):
    payslip_number: str
    period_start_date: date
    period_end_date: date
    payment_date: date
    total_working_days: int
    days_present: Decimal
    days_absent: Decimal = Decimal('0')
    days_on_leave: Decimal = Decimal('0')
    paid_days: Decimal
    lop_days: Decimal = Decimal('0')
    lop_amount: Decimal = Decimal('0')
    basic_salary: Decimal
    gross_salary: Decimal
    total_earnings: Decimal
    total_deductions: Decimal
    net_salary: Decimal
    monthly_ctc: Decimal
    status: PayslipStatus = PayslipStatus.GENERATED

class PayslipSchema(PayslipBase):
    uuid: UUID4
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

class PayslipListResponse(PaginatedResponse[List[PayslipSchema]]):
    pass

class PayslipResponse(BaseModel):
    success: bool
    message: str
    data: Optional[PayslipSchema] = None

class PayslipHoldUpdate(BaseModel):
    hold_reason: str = Field(..., min_length=1)

class PayslipReverseCreate(BaseModel):
    reversal_reason: str = Field(..., min_length=1)

class BulkEmailRequest(BaseModel):
    payslip_uuids: List[UUID4]