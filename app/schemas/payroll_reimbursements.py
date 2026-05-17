from typing import List, Optional, Generic, TypeVar
from pydantic import BaseModel, UUID4, Field
from datetime import date, datetime
from decimal import Decimal
from app.models.payroll import ReimbursementStatus

T = TypeVar("T")

class PaginatedResponse(BaseModel, Generic[T]):
    success: bool
    message: str
    data: T
    pagination: dict

class ReimbursementCategoryBase(BaseModel):
    category_code: str
    category_name: str
    description: Optional[str] = None
    max_claim_per_month: Optional[Decimal] = None
    max_claim_per_year: Optional[Decimal] = None
    max_claim_per_transaction: Optional[Decimal] = None
    requires_approval: bool = True
    approval_limit: Optional[Decimal] = None
    requires_receipt: bool = True
    receipt_mandatory_above: Optional[Decimal] = None
    is_taxable: bool = False
    is_active: bool = True

class ReimbursementCategoryCreate(ReimbursementCategoryBase):
    pass

class ReimbursementCategoryUpdate(BaseModel):
    category_code: Optional[str] = None
    category_name: Optional[str] = None
    description: Optional[str] = None
    max_claim_per_month: Optional[Decimal] = None
    max_claim_per_year: Optional[Decimal] = None
    max_claim_per_transaction: Optional[Decimal] = None
    requires_approval: Optional[bool] = None
    approval_limit: Optional[Decimal] = None
    requires_receipt: Optional[bool] = None
    receipt_mandatory_above: Optional[Decimal] = None
    is_taxable: Optional[bool] = None
    is_active: Optional[bool] = None

class ReimbursementCategorySchema(ReimbursementCategoryBase):
    uuid: UUID4
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

class ReimbursementClaimBase(BaseModel):
    category_uuid: UUID4
    claimed_amount: Decimal
    expense_date: date
    description: str
    merchant_name: Optional[str] = None
    receipt_urls: Optional[List[str]] = None

class ReimbursementClaimCreate(ReimbursementClaimBase):
    pass

class ReimbursementClaimUpdate(BaseModel):
    claimed_amount: Optional[Decimal] = None
    expense_date: Optional[date] = None
    description: Optional[str] = None
    merchant_name: Optional[str] = None
    receipt_urls: Optional[List[str]] = None

class ReimbursementApproveUpdate(BaseModel):
    approved_amount: Optional[Decimal] = None
    approver_comments: Optional[str] = None

class ReimbursementRejectUpdate(BaseModel):
    rejection_reason: Optional[str] = None

class ReimbursementClaimSchema(BaseModel):
    uuid: UUID4
    claim_number: str
    claim_date: date
    claimed_amount: Decimal
    approved_amount: Optional[Decimal] = None
    expense_date: date
    description: str
    merchant_name: Optional[str] = None
    status: ReimbursementStatus
    receipt_urls: Optional[List[str]] = None
    approver_comments: Optional[str] = None
    rejection_reason: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    category: Optional[ReimbursementCategorySchema] = None

    class Config:
        from_attributes = True

class ReimbursementSummarySchema(BaseModel):
    total_claims: int
    pending_approval_claims: int
    approved_amount: Decimal
    rejected_claims: int

    class Config:
        from_attributes = True

class ReimbursementClaimListResponse(PaginatedResponse[List[ReimbursementClaimSchema]]):
    summary: Optional[ReimbursementSummarySchema] = None

class ReimbursementCategoryListResponse(PaginatedResponse[List[ReimbursementCategorySchema]]):
    pass

class ReimbursementClaimResponse(BaseModel):
    success: bool
    message: str
    data: Optional[ReimbursementClaimSchema] = None