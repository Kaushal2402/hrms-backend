from typing import List, Optional
from pydantic import BaseModel, UUID4
from datetime import date, datetime
from decimal import Decimal
from app.schemas.department import PaginatedResponse

class PayrollJournalEntryLineBase(BaseModel):
    account_code: str
    account_name: str
    account_type: str
    debit_amount: Decimal = Decimal('0')
    credit_amount: Decimal = Decimal('0')
    description: Optional[str] = None
    cost_center_id: Optional[int] = None
    department_id: Optional[int] = None
    location_id: Optional[int] = None
    component_id: Optional[int] = None

class PayrollJournalEntryLineSchema(PayrollJournalEntryLineBase):
    id: int
    journal_entry_id: int
    line_number: int
    created_at: datetime

    class Config:
        from_attributes = True

class PayrollJournalEntryBase(BaseModel):
    payroll_period_id: int
    entry_number: str
    entry_date: date
    accounting_period: str
    financial_year: str
    entry_type: str
    narration: Optional[str] = None

class PayrollJournalEntryCreate(BaseModel):
    payroll_period_id: int
    entry_type: str

class PayrollJournalEntryUpdate(BaseModel):
    narration: Optional[str] = None
    status: Optional[str] = None

class PayrollJournalEntrySchema(PayrollJournalEntryBase):
    uuid: UUID4
    id: int
    total_debit: Decimal
    total_credit: Decimal
    status: str
    is_exported: bool
    exported_at: Optional[datetime] = None
    export_reference: Optional[str] = None
    is_reversed: bool
    reversed_at: Optional[datetime] = None
    reversal_entry_id: Optional[int] = None
    created_at: datetime
    updated_at: datetime
    lines: List[PayrollJournalEntryLineSchema] = []

    class Config:
        from_attributes = True

class PayrollJournalEntryResponse(BaseModel):
    success: bool
    message: str
    data: Optional[PayrollJournalEntrySchema] = None

class PayrollJournalEntryListResponse(PaginatedResponse[List[PayrollJournalEntrySchema]]):
    pass

class JournalEntryReverseCreate(BaseModel):
    reversal_reason: str