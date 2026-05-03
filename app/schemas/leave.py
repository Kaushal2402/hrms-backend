from typing import List, Optional, Any
from datetime import date
from decimal import Decimal
from pydantic import UUID4, BaseModel, field_validator, model_validator
from app.models.attendance import LeaveAccrualType, LeaveUnitType

from app.schemas.department import PaginatedResponse
from app.schemas.employee import EmployeeSummarySchema
from datetime import datetime

class LeaveTypeSchema(BaseModel):
    uuid: UUID4
    leave_code: str
    leave_name: str
    description: Optional[str] = None
    is_paid: bool
    is_encashable: bool
    is_carry_forward: bool
    max_carry_forward: Optional[Decimal] = None
    accrual_type: LeaveAccrualType
    accrual_rate: Decimal
    accrual_start_month: Optional[int] = None
    max_balance: Optional[Decimal] = None
    min_balance_for_application: Decimal
    allow_negative_balance: bool
    max_negative_balance: Optional[Decimal] = None
    min_leaves_per_application: Decimal
    max_leaves_per_application: Optional[Decimal] = None
    min_advance_days: int
    max_backdated_days: int
    unit_type: LeaveUnitType
    max_consecutive_days: Optional[int] = None
    include_weekends: bool
    include_holidays: bool
    documentation_required: bool
    documentation_required_after_days: Optional[int] = None
    requires_approval: bool
    approval_levels: int
    gender_specific: Optional[str] = None
    applicable_during_probation: bool
    available_after_months: int
    color_code: Optional[str] = None
    display_order: int
    is_active: bool
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

class LeaveTypeListResponse(PaginatedResponse[List[LeaveTypeSchema]]):
    pass

class LeaveTypeCreate(BaseModel):
    leave_code: str
    leave_name: str
    description: Optional[str] = None
    is_paid: bool = True
    is_encashable: bool = False
    is_carry_forward: bool = False
    max_carry_forward: Optional[Decimal] = None
    accrual_type: LeaveAccrualType
    accrual_rate: Decimal
    accrual_start_month: Optional[int] = None
    max_balance: Optional[Decimal] = None
    min_balance_for_application: Decimal = Decimal('0')
    allow_negative_balance: bool = False
    max_negative_balance: Optional[Decimal] = None
    min_leaves_per_application: Decimal = Decimal('0.5')
    max_leaves_per_application: Optional[Decimal] = None
    min_advance_days: int = 0
    max_backdated_days: int = 0
    unit_type: LeaveUnitType = LeaveUnitType.FULL_DAY
    max_consecutive_days: Optional[int] = None
    include_weekends: bool = False
    include_holidays: bool = False
    documentation_required: bool = False
    documentation_required_after_days: Optional[int] = None
    requires_approval: bool = True
    approval_levels: int = 1
    gender_specific: Optional[str] = None
    applicable_during_probation: bool = False
    available_after_months: int = 0
    color_code: Optional[str] = None
    display_order: int = 0
    is_active: bool = True

class LeaveTypeUpdate(BaseModel):
    leave_code: Optional[str] = None
    leave_name: Optional[str] = None
    description: Optional[str] = None
    is_paid: Optional[bool] = None
    is_encashable: Optional[bool] = None
    is_carry_forward: Optional[bool] = None
    max_carry_forward: Optional[Decimal] = None
    accrual_type: Optional[LeaveAccrualType] = None
    accrual_rate: Optional[Decimal] = None
    accrual_start_month: Optional[int] = None
    max_balance: Optional[Decimal] = None
    min_balance_for_application: Optional[Decimal] = None
    allow_negative_balance: Optional[bool] = None
    max_negative_balance: Optional[Decimal] = None
    min_leaves_per_application: Optional[Decimal] = None
    max_leaves_per_application: Optional[Decimal] = None
    min_advance_days: Optional[int] = None
    max_backdated_days: Optional[int] = None
    unit_type: Optional[LeaveUnitType] = None
    max_consecutive_days: Optional[int] = None
    include_weekends: Optional[bool] = None
    include_holidays: Optional[bool] = None
    documentation_required: Optional[bool] = None
    documentation_required_after_days: Optional[int] = None
    requires_approval: Optional[bool] = None
    approval_levels: Optional[int] = None
    gender_specific: Optional[str] = None
    applicable_during_probation: Optional[bool] = None
    available_after_months: Optional[int] = None
    color_code: Optional[str] = None
    display_order: Optional[int] = None
    is_active: Optional[bool] = None

class LeaveTypeResponse(BaseModel):
    success: bool
    message: str
    data: Optional[LeaveTypeSchema] = None

class LeaveTypeLookupSchema(BaseModel):
    uuid: UUID4
    leave_code: str
    leave_name: str

    class Config:
        from_attributes = True

class LeaveTypeLookupResponse(BaseModel):
    success: bool
    message: str
    data: List[LeaveTypeLookupSchema]

class LeavePolicySchema(BaseModel):
    uuid: UUID4
    policy_name: str
    description: Optional[str] = None
    applicable_to: Optional[str] = None
    department_uuids: Optional[List[UUID4]] = None
    location_uuids: Optional[List[UUID4]] = None
    employment_types: Optional[Any] = None
    effective_from: date
    effective_to: Optional[date] = None
    is_active: bool
    is_default: bool
    created_at: datetime
    updated_at: datetime
    mappings: List['LeavePolicyMappingSchema'] = []

    class Config:
        from_attributes = True

class LeavePolicyMappingSchema(BaseModel):
    id: int
    leave_type: LeaveTypeSchema
    annual_quota: Optional[Decimal] = None
    accrual_rate_override: Optional[Decimal] = None
    is_active: bool

    class Config:
        from_attributes = True

# To resolve circular reference
LeavePolicySchema.update_forward_refs()

class LeavePolicyListResponse(PaginatedResponse[List[LeavePolicySchema]]):
    pass

class LeavePolicyMappingCreate(BaseModel):
    leave_type_uuid: UUID4
    annual_quota: Optional[Decimal] = None
    accrual_rate_override: Optional[Decimal] = None
    is_active: bool = True

class LeavePolicyCreate(BaseModel):
    policy_name: str
    description: Optional[str] = None
    applicable_to: Optional[str] = "all"
    department_uuids: Optional[List[UUID4]] = None
    location_uuids: Optional[List[UUID4]] = None
    employment_types: Optional[List[str]] = None
    effective_from: date
    effective_to: Optional[date] = None
    is_active: bool = True
    is_default: bool = False
    mappings: List[LeavePolicyMappingCreate] = []

    @model_validator(mode='after')
    def validate_dates(self) -> 'LeavePolicyCreate':
        if self.effective_from and self.effective_to:
            if self.effective_from >= self.effective_to:
                raise ValueError("Effective From date must be before Effective To date")
        return self

class LeavePolicyResponse(BaseModel):
    success: bool
    message: str
    data: Optional[LeavePolicySchema] = None

class LeavePolicyUpdate(BaseModel):
    policy_name: Optional[str] = None
    description: Optional[str] = None
    applicable_to: Optional[str] = None
    department_uuids: Optional[List[UUID4]] = None
    location_uuids: Optional[List[UUID4]] = None
    employment_types: Optional[List[str]] = None
    effective_from: Optional[date] = None
    effective_to: Optional[date] = None
    is_active: Optional[bool] = None
    is_default: Optional[bool] = None
    mappings: Optional[List[LeavePolicyMappingCreate]] = None

    @model_validator(mode='after')
    def validate_dates(self) -> 'LeavePolicyUpdate':
        from_date = self.effective_from
        to_date = self.effective_to
        
        if from_date and to_date:
            if from_date >= to_date:
                raise ValueError("Effective From date must be before Effective To date")
        return self

class LeaveBalanceSchema(BaseModel):
    uuid: UUID4
    leave_type: LeaveTypeSchema
    balance_year: int
    period_start_date: date
    period_end_date: date
    opening_balance: Decimal
    brought_forward: Decimal
    accrued: Decimal
    credited: Decimal
    used: Decimal
    pending_approval: Decimal
    adjusted: Decimal
    encashed: Decimal
    lapsed: Decimal
    available_balance: Decimal
    total_balance: Decimal
    last_accrual_date: Optional[date] = None

    class Config:
        from_attributes = True

class LeaveBalanceListResponse(BaseModel):
    success: bool
    message: str
    data: List[LeaveBalanceSchema]

class LeaveCreditCreate(BaseModel):
    employee_uuid: UUID4
    leave_type_uuid: UUID4
    days: Decimal
    reason: str
    year: Optional[int] = None

class LeaveDebitCreate(BaseModel):
    employee_uuid: UUID4
    leave_type_uuid: UUID4
    days: Decimal
    reason: str
    year: Optional[int] = None

class LeaveBalanceResponse(BaseModel):
    success: bool
    message: str
    data: Optional[LeaveBalanceSchema] = None

class EmployeeLeaveSummarySchema(BaseModel):
    employee: EmployeeSummarySchema
    leave_balances: List[LeaveBalanceSchema]

class EmployeeLeaveListResponse(PaginatedResponse[List[EmployeeLeaveSummarySchema]]):
    pass

class AccrualProcessRequest(BaseModel):
    accrual_date: date
    employee_uuids: Optional[List[UUID4]] = None

class AccrualSummary(BaseModel):
    total_employees_processed: int
    total_accruals_created: int
    errors: List[str] = []

class AccrualProcessResponse(BaseModel):
    success: bool
    message: str
    data: AccrualSummary

class LeaveAccrualHistorySchema(BaseModel):
    uuid: UUID4
    leave_type: LeaveTypeSchema
    accrual_date: date
    accrual_period: Optional[str] = None
    accrued_days: Decimal
    transaction_type: str
    remarks: Optional[str] = None
    balance_after: Optional[Decimal] = None

    class Config:
        from_attributes = True

class LeaveAccrualHistoryListResponse(PaginatedResponse[List[LeaveAccrualHistorySchema]]):
    pass

class CarryForwardRequest(BaseModel):
    from_year: int
    to_year: int
    employee_uuids: Optional[List[UUID4]] = None

class CarryForwardSummary(BaseModel):
    total_employees_processed: int
    total_records_carried_forward: int
    total_days_carried_forward: Decimal
    errors: List[str] = []

class CarryForwardResponse(BaseModel):
    success: bool
    message: str
    data: CarryForwardSummary

# ==========================
# Leave Application Schemas
# ==========================

class LeaveApplicationBase(BaseModel):
    leave_type_uuid: UUID4
    from_date: date
    to_date: date
    is_half_day: bool = False
    half_day_session: Optional[str] = None  # 'first_half', 'second_half'
    reason: str
    reason_category: Optional[str] = None
    contact_address: Optional[str] = None
    contact_phone: Optional[str] = None
    remarks: Optional[str] = None

class LeaveApplicationCreate(LeaveApplicationBase):
    employee_uuid: UUID4
    compoff_application_uuids: Optional[List[UUID4]] = None
    attachment_urls: Optional[List[str]] = None

class LeaveApplicationUpdate(BaseModel):
    leave_type_uuid: Optional[UUID4] = None
    from_date: Optional[date] = None
    to_date: Optional[date] = None
    is_half_day: Optional[bool] = None
    half_day_session: Optional[str] = None
    reason: Optional[str] = None
    reason_category: Optional[str] = None
    contact_address: Optional[str] = None
    contact_phone: Optional[str] = None
    attachment_urls: Optional[List[str]] = None
    remarks: Optional[str] = None

class LeaveApprovalHistorySchema(BaseModel):
    approval_level: int
    approver: EmployeeSummarySchema
    action: str
    action_date: datetime
    comments: Optional[str] = None

    class Config:
        from_attributes = True

class LeaveApplicationSchema(BaseModel):
    uuid: UUID4
    application_number: str
    application_date: date
    from_date: date
    to_date: date
    total_days: Decimal
    is_half_day: bool
    half_day_session: Optional[str] = None
    reason: str
    reason_category: Optional[str] = None
    status: str
    
    # Relationships
    employee: EmployeeSummarySchema
    leave_type: LeaveTypeSchema
    current_approver: Optional[EmployeeSummarySchema] = None
    approved_by_user: Optional[EmployeeSummarySchema] = None
    approved_at: Optional[datetime] = None
    rejected_by_user: Optional[EmployeeSummarySchema] = None
    rejected_at: Optional[datetime] = None
    
    approval_history: List[LeaveApprovalHistorySchema] = []
    
    rejection_reason: Optional[str] = None
    remarks: Optional[str] = None
    attachment_urls: Optional[List[str]] = None
    
    created_at: datetime
    updated_at: datetime

    @field_validator('attachment_urls', mode='before')
    @classmethod
    def format_attachment_urls(cls, v):
        if not v:
            return v
        from app.utils.upload import get_file_url
        if isinstance(v, list):
            return [get_file_url(path) for path in v]
        return v

    class Config:
        from_attributes = True

class LeaveApplicationListResponse(PaginatedResponse[List[LeaveApplicationSchema]]):
    pass

class LeaveApplicationResponse(BaseModel):
    success: bool
    message: str
    data: Optional[LeaveApplicationSchema] = None

class LeaveActionRequest(BaseModel):
    comments: Optional[str] = None

class LeaveCalendarEvent(BaseModel):
    uuid: UUID4
    employee_name: str
    employee_uuid: UUID4
    leave_type_name: str
    from_date: date
    to_date: date
    status: str
    is_half_day: bool
    total_days: Decimal

class LeaveCalendarResponse(BaseModel):
    success: bool
    message: str
    data: List[LeaveCalendarEvent]

class LeaveConflictCheckRequest(BaseModel):
    employee_uuid: UUID4
    from_date: date
    to_date: date

class TeamAvailabilitySchema(BaseModel):
    total_team_members: int
    members_on_leave_count: int
    availability_percentage: float
    members_on_leave: List[EmployeeSummarySchema]

class LeaveConflictCheckResponse(BaseModel):
    success: bool
    message: str
    has_own_conflict: bool
    conflicting_applications: List[LeaveApplicationSchema]
    team_availability: TeamAvailabilitySchema

class CompensatoryOffSchema(BaseModel):
    uuid: UUID4
    employee: EmployeeSummarySchema
    worked_date: date
    comp_off_days: Decimal
    source_type: str
    reason: Optional[str] = None
    credited_date: date
    expiry_date: date
    is_utilized: bool
    is_expired: bool
    utilized_days: Decimal
    remaining_days: Decimal
    utilized_at: Optional[datetime] = None
    leave_application_uuid: Optional[UUID4] = None

    class Config:
        from_attributes = True

class CompensatoryOffListResponse(PaginatedResponse[List[CompensatoryOffSchema]]):
    pass

class CompensatoryOffCreate(BaseModel):
    employee_uuid: UUID4
    worked_date: date
    comp_off_days: Decimal
    source_type: str # 'weekend_work', 'holiday_work', 'overtime'
    reason: Optional[str] = None
    expiry_days: Optional[int] = 90

class CompensatoryOffResponse(BaseModel):
    success: bool
    message: str
    data: Optional[CompensatoryOffSchema] = None

class CompensatoryOffSummary(BaseModel):
    total_earned: Decimal
    total_utilized: Decimal
    total_expired: Decimal
    available_balance: Decimal

class EmployeeCompOffResponse(BaseModel):
    success: bool
    message: str
    data: CompensatoryOffSummary

class EmployeeCompOffListResponse(PaginatedResponse[List[CompensatoryOffSchema]]):
    summary: Optional[CompensatoryOffSummary] = None

class CompensatoryOffUtilizeRequest(BaseModel):
    leave_application_uuid: UUID4
    utilized_days: Decimal

class LeaveEncashmentSchema(BaseModel):
    uuid: UUID4
    encashment_number: str
    encashment_date: date
    employee: EmployeeSummarySchema
    leave_type: LeaveTypeSchema
    available_days: Decimal
    encashment_days: Decimal
    per_day_salary: Decimal
    encashment_amount: Decimal
    is_taxable: bool
    tax_deducted: Decimal
    net_amount: Decimal
    status: str
    approved_by_user: Optional[EmployeeSummarySchema] = None
    approved_at: Optional[datetime] = None
    rejection_reason: Optional[str] = None
    is_paid: bool
    payment_date: Optional[date] = None
    payment_reference: Optional[str] = None
    remarks: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True

class LeaveEncashmentListResponse(PaginatedResponse[List[LeaveEncashmentSchema]]):
    pass

class LeaveEncashmentCreate(BaseModel):
    employee_uuid: UUID4
    leave_type_uuid: UUID4
    encashment_days: Decimal
    remarks: Optional[str] = None

class LeaveEncashmentResponse(BaseModel):
    success: bool
    message: str
    data: Optional[LeaveEncashmentSchema] = None

class LeaveEncashmentApprove(BaseModel):
    approved_amount: Optional[Decimal] = None
    comments: Optional[str] = None

class LeaveEncashmentReject(BaseModel):
    rejection_reason: str

class LeaveEncashmentMarkPaid(BaseModel):
    payment_date: date
    payment_reference: Optional[str] = None

class BulkLeaveApprovalRequest(BaseModel):
    application_ids: List[UUID4]
    comments: Optional[str] = None

class BulkLeaveApprovalSummary(BaseModel):
    total_records: int
    success_count: int
    error_count: int
    errors: List[dict] = []

class BulkLeaveApprovalResponse(BaseModel):
    success: bool
    message: str
    data: BulkLeaveApprovalSummary

class BulkLeaveRejectRequest(BaseModel):
    application_ids: List[UUID4]
    rejection_reason: str

class LeavePayrollExportRequest(BaseModel):
    from_date: date
    to_date: date
    include_encashments: bool = True

class EmployeeLeavePayrollData(BaseModel):
    employee_uuid: UUID4
    employee_code: Optional[str] = None
    employee_name: str
    leave_summaries: List[dict] = [] # List of {type: str, days: float, is_paid: bool}
    total_unpaid_days: float = 0
    total_paid_days: float = 0
    total_encashment_days: float = 0
    total_encashment_amount: Decimal = Decimal('0')

class LeavePayrollExportResponse(BaseModel):
    success: bool
    message: str
    data: List[EmployeeLeavePayrollData]
