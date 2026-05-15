from typing import List, Optional, Generic, TypeVar
from pydantic import BaseModel, UUID4, Field
from datetime import date, datetime
from decimal import Decimal
from app.models.payroll import PayFrequency

T = TypeVar("T")

class PaginatedResponse(BaseModel, Generic[T]):
    success: bool
    message: str
    data: T
    pagination: dict

class EmployeeBriefSchema(BaseModel):
    uuid: UUID4
    first_name: str
    last_name: str
    employee_code: str
    
    class Config:
        from_attributes = True

class TemplateBriefSchema(BaseModel):
    uuid: UUID4
    template_name: str
    template_code: str
    
    class Config:
        from_attributes = True

class BankAccountBriefSchema(BaseModel):
    uuid: UUID4
    bank_name: str
    account_number: str
    
    class Config:
        from_attributes = True

class EmployeeSalaryBase(BaseModel):
    annual_ctc: Decimal
    monthly_ctc: Decimal
    monthly_gross: Decimal
    monthly_net: Decimal
    pay_frequency: PayFrequency
    currency: str = "INR"
    payment_mode: str = "bank_transfer"
    effective_from: date

class EmployeeSalaryCreate(EmployeeSalaryBase):
    employee_uuid: UUID4
    template_uuid: Optional[UUID4] = None
    bank_account_uuid: Optional[UUID4] = None

class EmployeeSalaryUpdate(BaseModel):
    annual_ctc: Optional[Decimal] = None
    monthly_ctc: Optional[Decimal] = None
    monthly_gross: Optional[Decimal] = None
    monthly_net: Optional[Decimal] = None
    pay_frequency: Optional[PayFrequency] = None
    payment_mode: Optional[str] = None

class SalaryHoldUpdate(BaseModel):
    hold_reason: Optional[str] = None
    hold_from_date: Optional[date] = None

class SalaryRevisionCreate(BaseModel):
    annual_ctc: Decimal
    template_uuid: Optional[UUID4] = None
    bank_account_uuid: Optional[UUID4] = None
    pay_frequency: Optional[PayFrequency] = PayFrequency.MONTHLY
    currency: Optional[str] = "INR"
    payment_mode: Optional[str] = "bank_transfer"
    revision_reason: str
    effective_from: date

class EmployeeSalarySchema(EmployeeSalaryBase):
    uuid: UUID4
    is_active: bool
    is_on_hold: bool
    employee: Optional[EmployeeBriefSchema] = None
    salary_template: Optional[TemplateBriefSchema] = None
    bank_account: Optional[BankAccountBriefSchema] = None
    created_at: datetime

    class Config:
        from_attributes = True

class EmployeeSalaryResponse(BaseModel):
    success: bool
    message: str
    data: Optional[EmployeeSalarySchema] = None

class EmployeeSalaryListResponse(PaginatedResponse[List[EmployeeSalarySchema]]):
    pass

class CTCComponent(BaseModel):
    component_name: str
    monthly: Decimal
    annual: Decimal

class CTCBreakdownResponse(BaseModel):
    success: bool
    message: str
    data: List[CTCComponent]