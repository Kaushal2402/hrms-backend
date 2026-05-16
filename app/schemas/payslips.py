from pydantic import BaseModel, Field
from typing import List, Optional, Any
from datetime import datetime, date
from decimal import Decimal
from uuid import UUID
from app.models.payroll import PayslipStatus

class PayslipBase(BaseModel):
    payslip_number: str
    period_start_date: date
    period_end_date: date
    payment_date: date
    total_working_days: int
    paid_days: Decimal
    gross_salary: Decimal
    total_earnings: Decimal
    total_deductions: Decimal
    net_salary: Decimal
    status: PayslipStatus
    is_published: bool

class PayslipCreate(PayslipBase):
    payroll_period_uuid: UUID
    employee_uuid: UUID
    employee_salary_uuid: UUID

class PayslipUpdate(BaseModel):
    status: Optional[PayslipStatus] = None
    is_published: Optional[bool] = None
    is_on_hold: Optional[bool] = None
    hold_reason: Optional[str] = None
    notes: Optional[str] = None

class PayslipInDBBase(PayslipBase):
    uuid: UUID
    employee_uuid: Optional[UUID] = None
    employee_name: Optional[str] = None
    period_name: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

class PayslipResponse(BaseModel):
    success: bool
    message: str
    data: PayslipInDBBase

class PayslipListResponse(BaseModel):
    success: bool
    message: str
    data: List[PayslipInDBBase]
    pagination: Optional[dict] = None

class PayslipDownloadResponse(BaseModel):
    success: bool
    message: str
    data: dict # Contains download URL or base64

class PayslipExportParams(BaseModel):
    period_uuid: Optional[UUID] = None
    employee_uuid: Optional[UUID] = None
    format: str = "csv" # csv, excel
