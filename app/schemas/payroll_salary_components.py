from typing import List, Optional, Generic, TypeVar
from pydantic import BaseModel, UUID4, Field
from datetime import datetime
from decimal import Decimal
from app.models.payroll import ComponentType, CalculationType, PayFrequency

T = TypeVar("T")

class PaginatedResponse(BaseModel, Generic[T]):
    success: bool
    message: str
    data: T
    pagination: dict

class SalaryComponentBase(BaseModel):
    component_code: str
    component_name: str
    component_type: ComponentType
    description: Optional[str] = None
    calculation_type: CalculationType
    calculation_value: Optional[Decimal] = None
    calculation_formula: Optional[str] = None
    based_on_component_ids: Optional[List[int]] = None
    is_taxable: bool = True
    is_part_of_gross: bool = True
    is_part_of_ctc: bool = True
    exemption_limit: Optional[Decimal] = None
    has_employer_contribution: bool = False
    employer_contribution_percentage: Optional[Decimal] = None
    has_employee_contribution: bool = False
    employee_contribution_percentage: Optional[Decimal] = None
    display_order: int = 0
    show_on_payslip: bool = True
    applicable_to_employee_types: Optional[List[str]] = None
    min_salary_for_applicability: Optional[Decimal] = None
    pay_frequency_override: Optional[PayFrequency] = None
    is_prorated: bool = True
    proration_based_on: Optional[str] = None
    statutory_component_type: Optional[str] = None
    is_active: bool = True

class SalaryComponentCreate(SalaryComponentBase):
    pass

class SalaryComponentUpdate(BaseModel):
    component_code: Optional[str] = None
    component_name: Optional[str] = None
    component_type: Optional[ComponentType] = None
    description: Optional[str] = None
    calculation_type: Optional[CalculationType] = None
    calculation_value: Optional[Decimal] = None
    calculation_formula: Optional[str] = None
    based_on_component_ids: Optional[List[int]] = None
    is_taxable: Optional[bool] = None
    is_part_of_gross: Optional[bool] = None
    is_part_of_ctc: Optional[bool] = None
    exemption_limit: Optional[Decimal] = None
    has_employer_contribution: Optional[bool] = None
    employer_contribution_percentage: Optional[Decimal] = None
    has_employee_contribution: Optional[bool] = None
    employee_contribution_percentage: Optional[Decimal] = None
    display_order: Optional[int] = None
    show_on_payslip: Optional[bool] = None
    applicable_to_employee_types: Optional[List[str]] = None
    min_salary_for_applicability: Optional[Decimal] = None
    pay_frequency_override: Optional[PayFrequency] = None
    is_prorated: Optional[bool] = None
    proration_based_on: Optional[str] = None
    statutory_component_type: Optional[str] = None
    is_active: Optional[bool] = None

class SalaryComponentSchema(SalaryComponentBase):
    id: int
    uuid: UUID4
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

class SalaryComponentResponse(BaseModel):
    success: bool
    message: str
    data: Optional[SalaryComponentSchema] = None

class SalaryComponentListResponse(PaginatedResponse[List[SalaryComponentSchema]]):
    pass