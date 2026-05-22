import uuid
from typing import List, Optional
from datetime import date, datetime
from decimal import Decimal
from pydantic import BaseModel, UUID4, Field
from app.schemas.department import PaginatedResponse

class StatutoryFormBase(BaseModel):
    form_type: str = Field(..., max_length=50)
    financial_year: str = Field(..., max_length=20)
    period: Optional[str] = Field(None, max_length=50)

class StatutoryFormCreate(StatutoryFormBase):
    employee_uuid: Optional[UUID4] = None
    amount: Optional[Decimal] = None
    notes: Optional[str] = None

class StatutoryFormFilingPayload(BaseModel):
    filing_reference: str = Field(..., min_length=1, max_length=100)
    acknowledgment_number: str = Field(..., min_length=1, max_length=100)
    notes: Optional[str] = None

class Form16BulkGeneratePayload(BaseModel):
    financial_year: str = Field(..., max_length=20)
    department_uuid: Optional[UUID4] = None

class StatutoryFormSchema(BaseModel):
    uuid: UUID4
    form_type: str
    form_name: str
    form_number: str
    financial_year: str
    period: Optional[str] = None
    period_start_date: Optional[date] = None
    period_end_date: Optional[date] = None
    filing_deadline: Optional[date] = None
    filing_status: str
    filed_at: Optional[datetime] = None
    filing_reference: Optional[str] = None
    acknowledgment_number: Optional[str] = None
    form_url: Optional[str] = None
    acknowledgment_url: Optional[str] = None
    amount: Optional[Decimal] = None
    notes: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

class StatutoryFormResponse(BaseModel):
    success: bool
    message: str
    data: Optional[StatutoryFormSchema] = None

class StatutoryFormListResponse(PaginatedResponse[List[StatutoryFormSchema]]):
    pass
