from typing import List, Optional, Generic, TypeVar
from pydantic import BaseModel, UUID4, Field, model_validator
from datetime import datetime, date
from decimal import Decimal
from app.models.payroll import TaxRegime
from app.schemas.employee import EmployeeSummarySchema

T = TypeVar("T")

class PaginatedResponse(BaseModel, Generic[T]):
    success: bool
    message: str
    data: T
    pagination: dict

class TaxDeclarationItemSchema(BaseModel):
    uuid: UUID4
    tax_section: str
    investment_type: str
    declared_amount: Decimal
    approved_amount: Optional[Decimal] = None
    section_limit: Optional[Decimal] = None
    proof_url: Optional[str] = None
    is_verified: bool
    is_rejected: bool
    rejection_reason: Optional[str] = None

    class Config:
        from_attributes = True

class TaxDeclarationSchema(BaseModel):
    uuid: UUID4
    financial_year: str
    tax_regime: TaxRegime
    declaration_type: str
    status: str
    total_declared_amount: Decimal
    total_approved_amount: Decimal
    is_locked: bool
    items: List[TaxDeclarationItemSchema] = []
    employee: Optional[EmployeeSummarySchema] = None

    class Config:
        from_attributes = True

class TaxDeclarationCreate(BaseModel):
    employee_uuid: UUID4
    financial_year: str
    tax_regime: TaxRegime
    declaration_type: str = "interim"

class TaxDeclarationUpdate(BaseModel):
    tax_regime: Optional[TaxRegime] = None
    declaration_type: Optional[str] = None

class TaxDeclarationItemCreate(BaseModel):
    tax_section: str
    investment_type: str
    declared_amount: Decimal
    section_limit: Optional[Decimal] = None
    proof_url: Optional[str] = None

class TaxDeclarationItemApproval(BaseModel):
    item_uuid: UUID4
    approved_amount: Decimal
    is_verified: bool
    is_rejected: bool = False
    rejection_reason: Optional[str] = None

class TaxCalculationSchema(BaseModel):
    uuid: UUID4
    financial_year: str
    tax_regime: TaxRegime
    gross_annual_income: Decimal
    taxable_income: Decimal
    total_tax: Decimal
    net_tax_payable: Decimal
    monthly_tds: Decimal
    standard_deduction: Decimal
    hra_exemption: Decimal
    lta_exemption: Decimal
    professional_tax: Decimal
    total_80c_deductions: Decimal
    total_80d_deductions: Decimal
    total_other_deductions: Decimal
    total_deductions: Decimal
    tax_slab_breakdown: Optional[List[dict]] = None
    deduction_breakdown: Optional[dict] = None

    class Config:
        from_attributes = True

class TaxRegimeComparisonSchema(BaseModel):
    financial_year: str
    old_regime_tax: Decimal
    new_regime_tax: Decimal
    recommended_regime: str

class CalculateTaxRequest(BaseModel):
    financial_year: str
    tax_regime: Optional[TaxRegime] = None
    projections: Optional[dict] = None

class BulkTaxCalculationRequest(BaseModel):
    financial_year: str
    employee_uuids: Optional[List[UUID4]] = None
    department_uuid: Optional[UUID4] = None
    location_uuid: Optional[UUID4] = None

class BulkTaxCalculationResponse(BaseModel):
    success: bool
    message: str
    total_processed: int

class TaxRegimeComparisonResponse(BaseModel):
    success: bool
    message: str
    data: Optional[TaxRegimeComparisonSchema] = None

class TaxDeclarationResponse(BaseModel):
    success: bool
    message: str
    data: Optional[TaxDeclarationSchema] = None

class TaxDeclarationSummary(BaseModel):
    total_declared_amount: Decimal
    total_approved_amount: Decimal
    active_declarations: int

class TaxDeclarationListResponse(PaginatedResponse[List[TaxDeclarationSchema]]):
    summary: Optional[TaxDeclarationSummary] = None

class TaxCalculationResponse(BaseModel):
    success: bool
    message: str
    data: Optional[TaxCalculationSchema] = None