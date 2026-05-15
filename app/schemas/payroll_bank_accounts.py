from pydantic import BaseModel, UUID4
from typing import Optional, List
from datetime import datetime
from decimal import Decimal
from app.schemas.department import PaginatedResponse

class EmployeeBankAccountBase(BaseModel):
    employee_id: int
    bank_name: str
    branch_name: Optional[str] = None
    account_number: str
    account_holder_name: str
    account_type: Optional[str] = None
    ifsc_code: Optional[str] = None
    swift_code: Optional[str] = None
    routing_number: Optional[str] = None
    sort_code: Optional[str] = None
    iban: Optional[str] = None
    is_primary: bool = False
    salary_percentage: Decimal = Decimal('100.00')
    salary_fixed_amount: Optional[Decimal] = None
    is_active: bool = True

class EmployeeBankAccountCreate(EmployeeBankAccountBase):
    pass

class EmployeeBankAccountUpdate(BaseModel):
    bank_name: Optional[str] = None
    branch_name: Optional[str] = None
    account_number: Optional[str] = None
    account_holder_name: Optional[str] = None
    account_type: Optional[str] = None
    ifsc_code: Optional[str] = None
    swift_code: Optional[str] = None
    routing_number: Optional[str] = None
    sort_code: Optional[str] = None
    iban: Optional[str] = None
    is_primary: Optional[bool] = None
    salary_percentage: Optional[Decimal] = None
    salary_fixed_amount: Optional[Decimal] = None
    is_active: Optional[bool] = None

class EmployeeBankAccountSchema(EmployeeBankAccountBase):
    uuid: UUID4
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

class EmployeeBankAccountResponse(BaseModel):
    success: bool
    message: str
    data: Optional[EmployeeBankAccountSchema] = None

class EmployeeBankAccountListResponse(PaginatedResponse[List[EmployeeBankAccountSchema]]):
    pass