from typing import List, Optional, Generic, TypeVar
from pydantic import BaseModel, UUID4, Field, model_validator
from datetime import date, datetime
from decimal import Decimal
from app.models.payroll import PayFrequency, CalculationType
from app.schemas.department import DepartmentSchema
from app.schemas.location import LocationSchema

T = TypeVar("T")

class PaginatedResponse(BaseModel, Generic[T]):
    success: bool
    message: str
    data: T
    pagination: dict

class SalaryTemplateComponentBase(BaseModel):
    component_uuid: UUID4
    calculation_type_override: Optional[CalculationType] = None
    calculation_value_override: Optional[Decimal] = None
    formula_override: Optional[str] = None
    min_value: Optional[Decimal] = None
    max_value: Optional[Decimal] = None
    display_order: int = 0
    is_mandatory: bool = True
    is_active: bool = True

class SalaryTemplateComponentSchema(SalaryTemplateComponentBase):
    id: int
    template_id: int
    component_id: int
    created_at: datetime
    
    class Config:
        from_attributes = True

class SalaryTemplateBase(BaseModel):
    template_code: str
    template_name: str
    description: Optional[str] = None
    applicable_to: Optional[str] = "all"
    grade_uuids: Optional[List[UUID4]] = None
    department_uuids: Optional[List[UUID4]] = None
    location_uuids: Optional[List[UUID4]] = None
    employment_types: Optional[List[str]] = None
    annual_ctc_min: Optional[Decimal] = None
    annual_ctc_max: Optional[Decimal] = None
    pay_frequency: PayFrequency = PayFrequency.MONTHLY
    is_active: bool = True
    is_default: bool = False
    effective_from: date
    effective_to: Optional[date] = None

class SalaryTemplateCreate(SalaryTemplateBase):
    components: List[SalaryTemplateComponentBase] = []

    @model_validator(mode='after')
    def validate_dates(self) -> 'SalaryTemplateCreate':
        if self.effective_from and self.effective_to:
            if self.effective_from >= self.effective_to:
                raise ValueError("effective_from must be before effective_to")
        return self

class SalaryTemplateUpdate(BaseModel):
    template_code: Optional[str] = None
    template_name: Optional[str] = None
    description: Optional[str] = None
    applicable_to: Optional[str] = None
    grade_uuids: Optional[List[UUID4]] = None
    department_uuids: Optional[List[UUID4]] = None
    location_uuids: Optional[List[UUID4]] = None
    employment_types: Optional[List[str]] = None
    annual_ctc_min: Optional[Decimal] = None
    annual_ctc_max: Optional[Decimal] = None
    pay_frequency: Optional[PayFrequency] = None
    is_active: Optional[bool] = None
    is_default: Optional[bool] = None
    effective_from: Optional[date] = None
    effective_to: Optional[date] = None
    components: Optional[List[SalaryTemplateComponentBase]] = None

class SalaryTemplateSchema(SalaryTemplateBase):
    uuid: UUID4
    departments: List[DepartmentSchema] = []
    locations: List[LocationSchema] = []
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

class SalaryTemplateDetailedSchema(SalaryTemplateSchema):
    components: List[SalaryTemplateComponentSchema] = []

class SalaryTemplateDetailedResponse(BaseModel):
    success: bool
    message: str
    data: Optional[SalaryTemplateDetailedSchema] = None

class SalaryTemplateResponse(BaseModel):
    success: bool
    message: str
    data: Optional[SalaryTemplateSchema] = None

class SalaryTemplateListResponse(PaginatedResponse[List[SalaryTemplateSchema]]):
    pass

class SalaryTemplateClone(BaseModel):
    new_template_name: str
    new_template_code: str

class SalaryTemplateComponentUpdate(BaseModel):
    components: List[SalaryTemplateComponentBase]

class PreviewRequest(BaseModel):
    annual_ctc: Decimal