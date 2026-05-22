from pydantic import BaseModel, Field
from typing import List, Optional
from decimal import Decimal
from datetime import date
from app.models.payroll import ComponentType

class BulkSalaryRevisionCreate(BaseModel):
    employee_uuids: List[str]
    revision_percentage: Decimal
    effective_date: date

class BulkComponentAdjustmentCreate(BaseModel):
    component_uuid: str
    employee_uuids: List[str]
    adjustment_amount: Optional[Decimal] = None
    adjustment_percentage: Optional[Decimal] = None

class ArrearCreate(BaseModel):
    employee_uuid: str
    arrear_type: str
    arrear_from_date: date
    arrear_to_date: date
    number_of_months: int
    arrear_amount: Decimal
    reason: str

class OneTimePaymentCreate(BaseModel):
    employee_uuid: str
    payment_type: str
    payment_name: str
    payment_amount: Decimal
    payment_reason: Optional[str] = None

class BulkOperationResult(BaseModel):
    success_count: int
    failure_count: int
    errors: List[dict]

    class Config:
        from_attributes = True