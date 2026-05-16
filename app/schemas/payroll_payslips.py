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
    
    # Financial Details
    total_employer_contributions: Decimal = Decimal('0')
    arrears_amount: Decimal = Decimal('0')
    arrears_description: Optional[str] = None
    one_time_payments: Decimal = Decimal('0')
    one_time_description: Optional[str] = None
    overtime_hours: Decimal = Decimal('0')
    overtime_amount: Decimal = Decimal('0')
    total_reimbursements: Decimal = Decimal('0')
    tax_deducted: Decimal = Decimal('0')
    
    # Lifecycle Flags
    is_published: bool = False
    published_at: Optional[datetime] = None
    is_on_hold: bool = False
    hold_reason: Optional[str] = None
    is_reversed: bool = False
    reversal_reason: Optional[str] = None
    reversed_at: Optional[datetime] = None
    
    # UI Metadata
    employee_name: Optional[str] = None
    employee_code: Optional[str] = None
    department_name: Optional[str] = None
    period_name: Optional[str] = None

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