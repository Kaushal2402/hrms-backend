from typing import List, Optional, Generic, TypeVar
from app.schemas.employee import EmployeeSummarySchema
from pydantic import BaseModel, UUID4, Field
from datetime import date, datetime
from decimal import Decimal
from app.models.payroll import LoanStatus

T = TypeVar("T")

class PaginatedResponse(BaseModel, Generic[T]):
    success: bool
    message: str
    data: T
    pagination: dict

class LoanBase(BaseModel):
    employee_uuid: UUID4
    loan_type: str
    loan_amount: Decimal
    interest_rate: Decimal = Decimal('0')
    total_payable: Decimal
    repayment_start_date: date
    number_of_installments: int
    monthly_installment: Decimal
    purpose: str
    notes: Optional[str] = None

class LoanCreate(LoanBase):
    pass

class LoanUpdate(BaseModel):
    loan_type: Optional[str] = None
    loan_amount: Optional[Decimal] = None
    interest_rate: Optional[Decimal] = None
    total_payable: Optional[Decimal] = None
    repayment_start_date: Optional[date] = None
    number_of_installments: Optional[int] = None
    monthly_installment: Optional[Decimal] = None
    purpose: Optional[str] = None
    notes: Optional[str] = None

class LoanReject(BaseModel):
    rejection_reason: str

class LoanDisbursementUpdate(BaseModel):
    disbursement_date: Optional[date] = None
    disbursement_mode: Optional[str] = None
    disbursement_reference: Optional[str] = None

class LoanSchema(LoanBase):
    uuid: UUID4
    loan_number: str
    status: LoanStatus
    
    # Progress
    installments_paid: int
    amount_paid: Decimal
    outstanding_amount: Decimal
    
    # Approval
    approved_at: Optional[datetime] = None
    approval_comments: Optional[str] = None
    rejection_reason: Optional[str] = None
    rejected_at: Optional[datetime] = None
    
    # Disbursement
    disbursement_date: Optional[date] = None
    disbursement_mode: Optional[str] = None
    disbursement_reference: Optional[str] = None
    
    # Completion & Audit
    completed_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime
    
    employee: Optional[EmployeeSummarySchema] = None

    class Config:
        from_attributes = True

class LoanResponse(BaseModel):
    success: bool
    message: str
    data: Optional[LoanSchema] = None

class LoanListResponse(PaginatedResponse[List[LoanSchema]]):
    pass

class EmployeeLoanSummary(BaseModel):
    total_sanctioned: Decimal
    outstanding_balance: Decimal
    total_repaid: Decimal
    monthly_emi_commitment: Decimal

class EmployeeLoanListResponse(PaginatedResponse[List[LoanSchema]]):
    summary: Optional[EmployeeLoanSummary] = None

class LoanRepaymentSchema(BaseModel):
    installment_number: int
    due_date: date
    principal_amount: Decimal
    interest_amount: Decimal
    total_amount: Decimal
    is_paid: bool
    paid_date: Optional[date] = None

    class Config:
        from_attributes = True

class LoanRepaymentListResponse(BaseModel):
    success: bool
    message: str
    data: List[LoanRepaymentSchema]