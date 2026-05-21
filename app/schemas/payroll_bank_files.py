from typing import List, Optional, Generic, TypeVar, Literal
from pydantic import BaseModel, UUID4, Field, constr, model_validator
from datetime import datetime, date
from decimal import Decimal
from app.models.payroll import PayrollStatus, BankFileStatus

T = TypeVar("T")

class PaginatedResponse(BaseModel, Generic[T]):
    success: bool
    message: str
    data: T
    pagination: dict

class BankFileRecordSchema(BaseModel):
    uuid: Optional[UUID4] = None
    employee_uuid: Optional[str] = None
    employee_name: str
    bank_account_number: str
    ifsc_code: Optional[str] = None
    bank_name: Optional[str] = None
    net_salary: Decimal
    payment_status: str
    utr_number: Optional[str] = None
    payment_date: Optional[date] = None

    class Config:
        from_attributes = True

class BankFileSchema(BaseModel):
    uuid: UUID4
    file_number: str
    file_name: str
    bank_name: Optional[str] = None
    file_format: str
    total_records: int
    total_amount: Decimal
    file_url: str
    status: BankFileStatus
    generated_at: datetime

    class Config:
        from_attributes = True

from typing_extensions import Self

class BankFileCreate(BaseModel):
    period_uuid : UUID4
    bank_format: Literal['NEFT', 'RTGS', 'CSV', 'Excel', 'Custom']
    bank_name: Optional[str] = None

    @model_validator(mode="after")
    def validate_bank_name(self) -> Self:
        if self.bank_format == "Custom" and not self.bank_name:
            raise ValueError("bank_name is required when bank_format is 'Custom'")
        return self

class UTRMappingItem(BaseModel):
    employee_uuid: UUID4
    utr_number: constr(min_length=1, max_length=50, pattern=r"^[a-zA-Z0-9\-]+$")

class BankConfirmationUpdate(BaseModel):
    utr_numbers: Optional[List[UTRMappingItem]] = None

    @model_validator(mode="after")
    def validate_utr_numbers(self) -> Self:
        if self.utr_numbers is not None and len(self.utr_numbers) == 0:
            raise ValueError("utr_numbers list cannot be empty when provided")
        return self

class BankFileListResponse(PaginatedResponse[List[BankFileSchema]]):
    pass

class BankFileResponse(BaseModel):
    success: bool
    message: str
    data: Optional[BankFileSchema] = None

class BankFileRecordListResponse(PaginatedResponse[List[BankFileRecordSchema]]):
    pass