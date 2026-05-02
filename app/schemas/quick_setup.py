from typing import List, Optional, Any
from pydantic import BaseModel, UUID4
from datetime import time
from decimal import Decimal

# ============================================================================
# TEMPLATE SCHEMAS
# ============================================================================

class DeptTemplateSchema(BaseModel):
    id: int
    department_code: str
    department_name: str
    description: Optional[str] = None

    class Config:
        from_attributes = True

class JobTitleTemplateSchema(BaseModel):
    id: int
    title_code: str
    title_name: str
    job_level: Optional[str] = None
    job_family: Optional[str] = None
    description: Optional[str] = None
    responsibilities: Optional[str] = None
    qualifications: Optional[str] = None

    class Config:
        from_attributes = True

class RoleTemplateSchema(BaseModel):
    id: int
    role_code: str
    role_name: str
    role_description: Optional[str] = None
    role_level: int
    scope: str
    color_code: Optional[str] = None
    icon: Optional[str] = None
    permission_codes: List[str]

    class Config:
        from_attributes = True

class ShiftTemplateSchema(BaseModel):
    id: int
    shift_code: str
    shift_name: str
    shift_type: str
    start_time: time
    end_time: time
    work_hours: Decimal
    break_hours: Decimal
    has_break: bool
    late_arrival_grace_minutes: int
    early_departure_grace_minutes: int
    week_off_days: Optional[List[int]]

    class Config:
        from_attributes = True

class AttPolicyTemplateSchema(BaseModel):
    id: int
    policy_name: str
    working_days_per_week: int
    working_hours_per_day: Decimal
    late_arrival_grace: int
    early_departure_grace: int
    overtime_enabled: bool
    regularization_allowed: bool

    class Config:
        from_attributes = True

class LeaveTypeTemplateSchema(BaseModel):
    id: int
    leave_code: str
    leave_name: str
    description: Optional[str] = None
    accrual_type: str
    accrual_rate: Decimal
    annual_quota: Decimal
    max_balance: Optional[Decimal] = None
    color_code: Optional[str] = None

    class Config:
        from_attributes = True

class LeavePolicyTemplateSchema(BaseModel):
    id: int
    policy_name: str
    description: Optional[str] = None
    leave_type_codes: List[str]

    class Config:
        from_attributes = True

class HolidayTemplateSchema(BaseModel):
    holiday_name: str
    holiday_date: Any # date
    holiday_type: str

    class Config:
        from_attributes = True

# ============================================================================
# AGGREGATED SUGGESTIONS
# ============================================================================

class IndustrySuggestionsData(BaseModel):
    industry_name: str
    departments: List[DeptTemplateSchema]
    job_titles: List[JobTitleTemplateSchema]
    roles: List[RoleTemplateSchema]
    shifts: List[ShiftTemplateSchema]
    attendance_policies: List[AttPolicyTemplateSchema]
    leave_types: List[LeaveTypeTemplateSchema]
    leave_policies: List[LeavePolicyTemplateSchema]
    holidays: List[HolidayTemplateSchema]
    location_suggestion: str

class IndustrySuggestionsResponse(BaseModel):
    success: bool
    message: str
    data: IndustrySuggestionsData

# ============================================================================
# QUICK SETUP EXECUTION
# ============================================================================

class QuickSetupRequest(BaseModel):
    department_ids: List[int]
    job_title_ids: List[int]
    role_ids: List[int]
    shift_ids: List[int]
    attendance_policy_ids: List[int]
    leave_type_ids: List[int]
    leave_policy_ids: List[int]
    selected_holidays: Optional[List[HolidayTemplateSchema]] = []
    setup_location: bool = True
    setup_holidays: bool = True

class QuickSetupJobResponse(BaseModel):
    success: bool
    message: str
    job_uuid: UUID4
    status: str
    progress_percentage: Optional[int] = 0
    logs: Optional[List[Any]] = []
