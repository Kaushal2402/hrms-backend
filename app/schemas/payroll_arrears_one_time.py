from typing import Optional, List, Generic, TypeVar
from pydantic import BaseModel, UUID4, Field
from datetime import datetime, date
from decimal import Decimal
from app.models.payroll import Arrear, OneTimePayment

T = TypeVar("T")

class PaginatedResponse(BaseModel, Generic[T]):
    success: bool
    message: str
    data: T
    pagination: dict

class EmployeeBasicInfo(BaseModel):
    uuid: UUID4
    employee_code: str
    first_name: str
    last_name: str
    work_email: str

    class Config:
        from_attributes = True

# ─── Arrear ───────────────────────────────────────────────────────────────────

class ArrearBase(BaseModel):
    arrear_type: str
    arrear_from_date: date
    arrear_to_date: date
    number_of_months: int
    arrear_amount: Decimal
    is_taxable: bool = True
    reason: str
    description: Optional[str] = None

class ArrearCreate(ArrearBase):
    employee_uuid: UUID4

class ArrearUpdate(BaseModel):
    arrear_type: Optional[str] = None
    arrear_amount: Optional[Decimal] = None
    reason: Optional[str] = None
    description: Optional[str] = None
    is_taxable: Optional[bool] = None

class ArrearSchema(ArrearBase):
    uuid: UUID4
    arrear_number: str
    status: str
    tax_deducted: Decimal
    employee: EmployeeBasicInfo
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

class ArrearResponse(BaseModel):
    success: bool
    message: str
    data: Optional[ArrearSchema] = None

class ArrearListResponse(PaginatedResponse[List[ArrearSchema]]):
    pass

# ─── OneTimePayment ───────────────────────────────────────────────────────────

class OneTimePaymentBase(BaseModel):
    payment_type: str
    payment_name: str
    payment_amount: Decimal
    is_taxable: bool = True
    description: Optional[str] = None
    payment_reason: Optional[str] = None

class OneTimePaymentCreate(OneTimePaymentBase):
    employee_uuid: UUID4

class OneTimePaymentUpdate(BaseModel):
    payment_type: Optional[str] = None
    payment_name: Optional[str] = None
    payment_amount: Optional[Decimal] = None
    description: Optional[str] = None
    payment_reason: Optional[str] = None

class OneTimePaymentSchema(OneTimePaymentBase):
    uuid: UUID4
    payment_number: str
    status: str
    tax_deducted: Decimal
    employee: EmployeeBasicInfo
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

class OneTimePaymentResponse(BaseModel):
    success: bool
    message: str
    data: Optional[OneTimePaymentSchema] = None

class OneTimePaymentListResponse(PaginatedResponse[List[OneTimePaymentSchema]]):
    pass
