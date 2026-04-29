from pydantic import BaseModel, UUID4, Field
from typing import Optional, List, Any
from datetime import datetime, time, date
import enum
from decimal import Decimal
from app.schemas.department import PaginatedResponse, PaginationData
from app.schemas.employee import EmployeeMinimalSchema
from app.models.attendance import (
    ShiftType, RegularizationStatus, OvertimeStatus, TimesheetStatus,
    DelegationType, CompensationType
)

class ShiftBase(BaseModel):
    shift_code: str
    shift_name: str
    shift_type: ShiftType
    description: Optional[str] = None
    
    # Shift Timing
    start_time: time
    end_time: time
    
    # Working Hours
    work_hours: Decimal
    break_hours: Decimal = Decimal('0.0')
    
    # Break Configuration
    has_break: bool = False
    break_start_time: Optional[time] = None
    break_end_time: Optional[time] = None
    break_duration_minutes: Optional[int] = None
    
    # Grace Period
    late_arrival_grace_minutes: int = 0
    early_departure_grace_minutes: int = 0
    
    # Overtime Settings
    overtime_applicable: bool = True
    overtime_threshold_minutes: int = 0
    
    # Half Day Settings
    half_day_hours: Optional[Decimal] = None
    
    # Week-off Configuration
    week_off_days: Optional[List[int]] = None # [0=Sunday, 1=Monday, ...]
    
    # Split Shift
    is_split_shift: bool = False
    split_start_time: Optional[time] = None
    split_end_time: Optional[time] = None
    
    # Night Shift
    is_night_shift: bool = False
    night_shift_allowance: Optional[Decimal] = None
    
    # Color Coding
    color_code: Optional[str] = None
    
    is_active: bool = True
    is_default: bool = False

class ShiftCreate(ShiftBase):
    pass

class ShiftUpdate(BaseModel):
    shift_code: Optional[str] = None
    shift_name: Optional[str] = None
    shift_type: Optional[ShiftType] = None
    description: Optional[str] = None
    start_time: Optional[time] = None
    end_time: Optional[time] = None
    work_hours: Optional[Decimal] = None
    break_hours: Optional[Decimal] = None
    has_break: Optional[bool] = None
    break_start_time: Optional[time] = None
    break_end_time: Optional[time] = None
    break_duration_minutes: Optional[int] = None
    late_arrival_grace_minutes: Optional[int] = None
    early_departure_grace_minutes: Optional[int] = None
    overtime_applicable: Optional[bool] = None
    overtime_threshold_minutes: Optional[int] = None
    half_day_hours: Optional[Decimal] = None
    week_off_days: Optional[List[int]] = None
    is_split_shift: Optional[bool] = None
    split_start_time: Optional[time] = None
    split_end_time: Optional[time] = None
    is_night_shift: Optional[bool] = None
    night_shift_allowance: Optional[Decimal] = None
    color_code: Optional[str] = None
    is_active: Optional[bool] = None
    is_default: Optional[bool] = None

class ShiftSchema(ShiftBase):
    uuid: UUID4
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

class ShiftListResponse(PaginatedResponse[List[ShiftSchema]]):
    pass

class ShiftResponse(BaseModel):
    success: bool
    message: str
    data: Optional[ShiftSchema] = None

# Shift Assignment Schemas
class ShiftAssignmentBase(BaseModel):
    effective_from: date
    effective_to: Optional[date] = None
    is_rotating: bool = False
    rotation_pattern: Optional[dict] = None
    is_active: bool = True

class ShiftAssignmentCreate(ShiftAssignmentBase):
    employee_uuid: UUID4
    shift_uuid: UUID4

class BulkShiftAssignmentCreate(ShiftAssignmentBase):
    employee_uuids: List[UUID4]
    shift_uuid: UUID4

class ShiftAssignmentUpdate(BaseModel):
    shift_uuid: Optional[UUID4] = None
    effective_from: Optional[date] = None
    effective_to: Optional[date] = None
    is_rotating: Optional[bool] = None
    rotation_pattern: Optional[dict] = None
    is_active: Optional[bool] = None

class ShiftAssignmentSchema(ShiftAssignmentBase):
    uuid: UUID4
    created_at: datetime
    updated_at: datetime
    
    # We will include these in the response
    employee: Optional[EmployeeMinimalSchema] = None
    shift: Optional[ShiftSchema] = None

    class Config:
        from_attributes = True

class ShiftAssignmentListResponse(PaginatedResponse[List[ShiftAssignmentSchema]]):
    pass

class ShiftAssignmentResponse(BaseModel):
    success: bool
    message: str
    data: Optional[ShiftAssignmentSchema] = None

class BulkShiftAssignmentResponse(BaseModel):
    success: bool
    message: str
    data: List[ShiftAssignmentSchema] = []

# Shift Roster Schemas
class ShiftRosterBase(BaseModel):
    roster_date: date
    actual_start_time: Optional[time] = None
    actual_end_time: Optional[time] = None
    is_week_off: bool = False
    is_working_on_week_off: bool = False
    is_published: bool = False
    notes: Optional[str] = None

class ShiftRosterCreate(ShiftRosterBase):
    employee_uuid: UUID4
    shift_uuid: UUID4

class ShiftRosterUpdate(BaseModel):
    employee_uuid: Optional[UUID4] = None
    shift_uuid: Optional[UUID4] = None
    roster_date: Optional[date] = None
    actual_start_time: Optional[time] = None
    actual_end_time: Optional[time] = None
    is_week_off: Optional[bool] = None
    is_working_on_week_off: Optional[bool] = None
    is_published: Optional[bool] = None
    notes: Optional[str] = None

class ShiftRosterSchema(ShiftRosterBase):
    uuid: UUID4
    created_at: datetime
    updated_at: datetime
    
    employee: Optional[EmployeeMinimalSchema] = None
    shift: Optional[ShiftSchema] = None

    class Config:
        from_attributes = True

class ShiftRosterListResponse(PaginatedResponse[List[ShiftRosterSchema]]):
    pass

class ShiftRosterResponse(BaseModel):
    success: bool
    message: str
    data: Optional[ShiftRosterSchema] = None

class BulkShiftRosterCreate(BaseModel):
    entries: List[ShiftRosterCreate]

class BulkShiftRosterResponse(BaseModel):
    success: bool
    message: str
    data: List[ShiftRosterSchema] = []

class RosterGenerationRequest(BaseModel):
    from_date: date
    to_date: date
    department_uuid: Optional[UUID4] = None
    location_uuid: Optional[UUID4] = None
    employee_uuids: Optional[List[UUID4]] = None
    overwrite_existing: bool = False
    publish_immediately: bool = False

class RosterPublishRequest(BaseModel):
    from_date: date
    to_date: date
    employee_uuids: Optional[List[UUID4]] = None
    department_uuid: Optional[UUID4] = None
    location_uuid: Optional[UUID4] = None

class SpecificRosterUnpublishRequest(BaseModel):
    roster_uuids: List[UUID4]

# Attendance Schemas
from app.models.attendance import AttendanceSource, CheckType

class AttendanceCheckIn(BaseModel):
    employee_uuid: UUID4
    timestamp: Optional[datetime] = None
    latitude: Optional[Decimal] = None
    longitude: Optional[Decimal] = None
    location_name: Optional[str] = None
    source: AttendanceSource
    device_id: Optional[str] = None

class AttendanceLogSchema(BaseModel):
    uuid: UUID4
    punch_time: datetime
    punch_date: date
    check_type: CheckType
    source: AttendanceSource
    device_id: Optional[str] = None
    location: Optional[str] = None
    latitude: Optional[Decimal] = None
    longitude: Optional[Decimal] = None
    is_processed: bool
    is_valid: bool
    
    employee: Optional[EmployeeMinimalSchema] = None

    class Config:
        from_attributes = True

class AttendanceLogListResponse(PaginatedResponse[List[AttendanceLogSchema]]):
    pass

class AttendanceCheckInResponse(BaseModel):
    success: bool
    message: str
    data: Optional[AttendanceLogSchema] = None

class AttendanceCheckOut(AttendanceCheckIn):
    pass

class AttendanceCheckOutResponse(BaseModel):
    success: bool
    message: str
    data: Optional[dict] = None # Will contain log and summary hours

class AttendanceBreak(BaseModel):
    employee_uuid: UUID4
    timestamp: Optional[datetime] = None
    source: AttendanceSource
    device_id: Optional[str] = None

class AttendanceBreakResponse(BaseModel):
    success: bool
    message: str
    data: Optional[AttendanceLogSchema] = None

class AttendanceBreakEndResponse(BaseModel):
    success: bool
    message: str
    data: Optional[dict] = None # Will contain log and break summary

class AttendanceCurrentStatusSchema(BaseModel):
    employee_uuid: UUID4
    is_checked_in: bool
    is_on_break: bool
    last_punch_type: Optional[CheckType] = None
    last_punch_time: Optional[datetime] = None
    attendance_date: Optional[date] = None
    total_work_hours: float = 0.0
    total_break_hours: float = 0.0
    net_work_hours: float = 0.0
    current_shift: Optional[ShiftSchema] = None

class AttendanceCurrentStatusResponse(BaseModel):
    success: bool
    message: str
    data: Optional[AttendanceCurrentStatusSchema] = None

from app.models.attendance import AttendanceStatus

class AttendanceRecordSchema(BaseModel):
    uuid: UUID4
    attendance_date: date
    shift_start_time: Optional[time] = None
    shift_end_time: Optional[time] = None
    first_check_in: Optional[datetime] = None
    last_check_out: Optional[datetime] = None
    total_work_hours: Optional[Decimal] = None
    break_hours: Optional[Decimal] = None
    net_work_hours: Optional[Decimal] = None
    status: AttendanceStatus
    is_late: bool
    late_by_minutes: int
    is_early_departure: bool
    early_departure_minutes: int
    is_manual_entry: bool = False
    manual_entry_reason: Optional[str] = None
    is_regularized: bool = False
    regularization_id: Optional[int] = None
    remarks: Optional[str] = None
    
    employee: Optional[EmployeeMinimalSchema] = None
    shift: Optional[ShiftSchema] = None

    class Config:
        from_attributes = True

class AttendanceRecordListResponse(PaginatedResponse[List[AttendanceRecordSchema]]):
    pass

class AttendanceRecordResponse(BaseModel):
    success: bool
    message: str
    data: Optional[AttendanceRecordSchema] = None

class ManualAttendanceCreate(BaseModel):
    employee_uuid: UUID4
    attendance_date: date
    check_in: datetime
    check_out: Optional[datetime] = None
    reason: str

class AttendanceRecordUpdate(BaseModel):
    status: Optional[AttendanceStatus] = None
    first_check_in: Optional[datetime] = None
    last_check_out: Optional[datetime] = None
    remarks: Optional[str] = None
    is_regularized: Optional[bool] = None
    total_work_hours: Optional[Decimal] = None
    break_hours: Optional[Decimal] = None
    net_work_hours: Optional[Decimal] = None

class EmployeeAttendanceSummary(BaseModel):
    total_days: int = 0
    present_days: int = 0
    absent_days: int = 0
    half_days: int = 0
    leave_days: int = 0
    holiday_days: int = 0
    late_days: int = 0
    early_departure_days: int = 0
    total_work_hours: float = 0.0
    total_break_hours: float = 0.0
    total_net_work_hours: float = 0.0

class EmployeeAttendanceResponse(BaseModel):
    success: bool
    message: str
    summary: Optional[EmployeeAttendanceSummary] = None
    pagination: Optional[dict] = None
    data: List[AttendanceRecordSchema]

class AttendanceSummaryResponse(BaseModel):
    success: bool
    message: str
    data: EmployeeAttendanceSummary

class DashboardEmployeeStatus(BaseModel):
    employee_uuid: UUID4
    employee_name: str
    employee_code: Optional[str] = None
    department_name: Optional[str] = None
    location_name: Optional[str] = None
    
    # Shift info
    shift_name: Optional[str] = None
    shift_start_time: Optional[time] = None
    shift_end_time: Optional[time] = None
    
    # Real-time status
    status: AttendanceStatus
    is_checked_in: bool = False
    is_on_break: bool = False
    first_check_in: Optional[datetime] = None
    last_check_out: Optional[datetime] = None
    
    # Performance metrics
    is_late: bool = False
    late_by_minutes: int = 0
    is_early_departure: bool = False
    early_departure_minutes: int = 0
    
    class Config:
        from_attributes = True

class AttendanceDashboardResponse(BaseModel):
    success: bool
    message: str
    date: date
    summary: dict
    data: List[DashboardEmployeeStatus]

class AttendanceLogProcessRequest(BaseModel):
    log_uuids: Optional[List[UUID4]] = None
    from_date: Optional[date] = None
    to_date: Optional[date] = None
    employee_uuids: Optional[List[UUID4]] = None

class AttendanceLogProcessResponse(BaseModel):
    success: bool
    message: str
    processed_logs_count: int
    updated_records_count: int
    errors: Optional[List[str]] = None

class AttendanceSyncRequest(BaseModel):
    device_id: str
    logs: List[dict] # Simplified for now, can be specific strict schema if needed

class AttendanceSyncResponse(BaseModel):
    success: bool
    message: str
    synced_count: int
    errors: Optional[List[str]] = None

# Biometric Sync Schemas (Pull)
class BiometricSyncRequest(BaseModel):
    device_id: str
    sync_from_timestamp: datetime

class BiometricSyncResponse(BaseModel):
    success: bool
    message: str
    synced_count: int
    error_count: int
    errors: Optional[List[str]] = None

# Regularization Schemas
class AttendanceRegularizationSchema(BaseModel):
    uuid: UUID4
    attendance_date: date
    original_check_in: Optional[datetime] = None
    original_check_out: Optional[datetime] = None
    requested_check_in: Optional[datetime] = None
    requested_check_out: Optional[datetime] = None
    reason: str
    reason_category: Optional[str] = None
    status: RegularizationStatus
    approver_id: Optional[int] = None
    approved_at: Optional[datetime] = None
    approver_comments: Optional[str] = None
    rejection_reason: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    
    employee: Optional[EmployeeMinimalSchema] = None
    approver: Optional[EmployeeMinimalSchema] = None

    class Config:
        from_attributes = True

class AttendanceRegularizationCreate(BaseModel):
    employee_uuid: UUID4
    attendance_date: date
    requested_check_in: Optional[datetime] = None
    requested_check_out: Optional[datetime] = None
    reason: str
    reason_category: Optional[str] = None
    attachment_urls: Optional[List[str]] = None

class AttendanceRegularizationListResponse(PaginatedResponse[List[AttendanceRegularizationSchema]]):
    pass

class AttendanceRegularizationResponse(BaseModel):
    success: bool
    message: str
    data: Optional[AttendanceRegularizationSchema] = None

class AttendanceRegularizationApproval(BaseModel):
    comments: Optional[str] = None

class AttendanceRegularizationRejection(BaseModel):
    rejection_reason: str

# Overtime Schemas
class OvertimeRequestSchema(BaseModel):
    uuid: UUID4
    attendance_date: date
    overtime_hours: Decimal
    overtime_start_time: Optional[datetime] = None
    overtime_end_time: Optional[datetime] = None
    is_pre_approved: bool
    reason: str
    work_description: Optional[str] = None
    compensation_type: Optional[CompensationType] = None
    status: OvertimeStatus
    approver_id: Optional[int] = None
    approved_at: Optional[datetime] = None
    approver_comments: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    
    employee: Optional[EmployeeMinimalSchema] = None
    approver: Optional[EmployeeMinimalSchema] = None

    class Config:
        from_attributes = True

class OvertimeRequestListResponse(PaginatedResponse[List[OvertimeRequestSchema]]):
    pass

class OvertimeRequestCreate(BaseModel):
    employee_uuid: UUID4
    attendance_date: date
    overtime_start_time: datetime
    overtime_end_time: datetime
    is_pre_approved: bool = False
    reason: str
    work_description: Optional[str] = None
    compensation_type: Optional[CompensationType] = CompensationType.paid

class OvertimeRequestResponse(BaseModel):
    success: bool
    message: str
    data: Optional[OvertimeRequestSchema] = None

class OvertimeRequestApproval(BaseModel):
    compensation_type: Optional[CompensationType] = None
    comments: Optional[str] = None

class OvertimeRequestRejection(BaseModel):
    rejection_reason: str

class OvertimeSummarySchema(BaseModel):
    total_hours: Decimal
    paid_hours: Decimal
    comp_off_hours: Decimal
    pending_hours: Decimal
    approved_hours: Decimal
    rejected_hours: Decimal
    request_count: int

class OvertimeSummaryResponse(BaseModel):
    success: bool
    message: str
    data: OvertimeSummarySchema

# Timesheet Schemas
class TimesheetEntrySchema(BaseModel):
    uuid: UUID4
    entry_date: date
    project_id: Optional[int] = None
    project_name: Optional[str] = None
    task_id: Optional[int] = None
    task_name: Optional[str] = None
    activity_description: Optional[str] = None
    hours_worked: Decimal
    is_billable: bool
    client_id: Optional[int] = None
    client_name: Optional[str] = None
    notes: Optional[str] = None

    class Config:
        from_attributes = True

class TimesheetSchema(BaseModel):
    uuid: UUID4
    period_start_date: date
    period_end_date: date
    period_type: str
    total_hours: Decimal
    billable_hours: Decimal
    non_billable_hours: Decimal
    status: TimesheetStatus
    submitted_at: Optional[datetime] = None
    approved_at: Optional[datetime] = None
    approver_comments: Optional[str] = None
    rejection_reason: Optional[str] = None
    rejected_at: Optional[datetime] = None
    notes: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    
    employee: Optional[EmployeeMinimalSchema] = None
    approver: Optional[EmployeeMinimalSchema] = None
    entries: List[TimesheetEntrySchema] = []

    class Config:
        from_attributes = True

class TimesheetListResponse(PaginatedResponse[List[TimesheetSchema]]):
    pass

class TimesheetResponse(BaseModel):
    success: bool
    message: str
    data: Optional[TimesheetSchema] = None

class TimesheetEntryCreate(BaseModel):
    entry_date: date
    project_id: Optional[int] = None
    project_name: Optional[str] = None
    task_id: Optional[int] = None
    task_name: Optional[str] = None
    activity_description: Optional[str] = None
    hours_worked: Decimal
    is_billable: bool = True
    client_id: Optional[int] = None
    client_name: Optional[str] = None
    notes: Optional[str] = None

class TimesheetCreate(BaseModel):
    employee_uuid: UUID4
    period_start_date: date
    period_end_date: date
    period_type: str = 'weekly' # 'weekly', 'monthly', etc.
    notes: Optional[str] = None
    entries: List[TimesheetEntryCreate]

class TimesheetUpdate(BaseModel):
    notes: Optional[str] = None
    entries: List[TimesheetEntryCreate]

class TimesheetApproval(BaseModel):
    comments: Optional[str] = None

class TimesheetRejection(BaseModel):
    rejection_reason: str

class TimesheetEntryResponse(BaseModel):
    success: bool
    message: str
    data: Optional[TimesheetEntrySchema] = None

class TimesheetEntryUpdate(BaseModel):
    entry_date: Optional[date] = None
    project_id: Optional[int] = None
    project_name: Optional[str] = None
    task_id: Optional[int] = None
    task_name: Optional[str] = None
    activity_description: Optional[str] = None
    hours_worked: Optional[Decimal] = None
    is_billable: Optional[bool] = None
    client_id: Optional[int] = None
    client_name: Optional[str] = None
    notes: Optional[str] = None
class TargetedEntitySchema(BaseModel):
    uuid: UUID4
    name: str

# Attendance Policy Schemas
class AttendancePolicyBase(BaseModel):
    policy_name: str
    description: Optional[str] = None
    working_days_per_week: int = 5
    working_hours_per_day: Decimal = Decimal('8.00')
    working_hours_per_week: Decimal = Decimal('40.00')
    late_arrival_grace: int = 0
    early_departure_grace: int = 0
    break_duration_minutes: int = 60
    is_break_mandatory: bool = False
    max_break_duration_minutes: Optional[int] = None
    half_day_threshold_hours: Decimal = Decimal('4.00')
    absent_threshold_hours: Decimal = Decimal('0.00')
    overtime_enabled: bool = True
    overtime_threshold_minutes: int = 0
    overtime_multiplier: Decimal = Decimal('1.5')
    max_overtime_hours_per_day: Optional[Decimal] = None
    max_overtime_hours_per_month: Optional[Decimal] = None
    regularization_allowed: bool = True
    max_regularizations_per_month: int = 3
    regularization_approval_required: bool = True
    late_deduction_enabled: bool = False
    late_deduction_after_minutes: int = 15
    late_deduction_per_occurrence: Optional[Decimal] = None
    applicable_to: Optional[str] = None # 'all', 'department', 'location'
    departments: List[TargetedEntitySchema] = []
    locations: List[TargetedEntitySchema] = []
    employment_types: Optional[List[str]] = None
    effective_from: date
    effective_to: Optional[date] = None
    is_active: bool = True
    is_default: bool = False

class AttendancePolicyCreate(AttendancePolicyBase):
    pass

class AttendancePolicyUpdate(BaseModel):
    policy_name: Optional[str] = None
    description: Optional[str] = None
    working_days_per_week: Optional[int] = None
    working_hours_per_day: Optional[Decimal] = None
    working_hours_per_week: Optional[Decimal] = None
    late_arrival_grace: Optional[int] = None
    early_departure_grace: Optional[int] = None
    break_duration_minutes: Optional[int] = None
    is_break_mandatory: Optional[bool] = None
    max_break_duration_minutes: Optional[int] = None
    half_day_threshold_hours: Optional[Decimal] = None
    absent_threshold_hours: Optional[Decimal] = None
    overtime_enabled: Optional[bool] = None
    overtime_threshold_minutes: Optional[int] = None
    overtime_multiplier: Optional[Decimal] = None
    max_overtime_hours_per_day: Optional[Decimal] = None
    max_overtime_hours_per_month: Optional[Decimal] = None
    regularization_allowed: Optional[bool] = None
    max_regularizations_per_month: Optional[int] = None
    regularization_approval_required: Optional[bool] = None
    late_deduction_enabled: Optional[bool] = None
    late_deduction_after_minutes: Optional[int] = None
    late_deduction_per_occurrence: Optional[Decimal] = None
    applicable_to: Optional[str] = None
    department_uuids: Optional[List[UUID4]] = None
    location_uuids: Optional[List[UUID4]] = None
    employment_types: Optional[List[str]] = None
    effective_from: Optional[date] = None
    effective_to: Optional[date] = None
    is_active: Optional[bool] = None
    is_default: Optional[bool] = None

class AttendancePolicySchema(AttendancePolicyBase):
    uuid: UUID4
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

class AttendancePolicyListResponse(PaginatedResponse[List[AttendancePolicySchema]]):
    pass

class AttendancePolicyResponse(BaseModel):
    success: bool
    message: str
    data: Optional[AttendancePolicySchema] = None

# Geofence Location Schemas
class GeofenceLocationBase(BaseModel):
    location_name: str
    location_uuid: Optional[UUID4] = None
    latitude: Decimal
    longitude: Decimal
    radius_meters: int
    address: Optional[str] = None
    is_active: bool = True

class GeofenceLocationCreate(GeofenceLocationBase):
    pass

class GeofenceLocationUpdate(BaseModel):
    location_name: Optional[str] = None
    location_uuid: Optional[UUID4] = None
    latitude: Optional[Decimal] = None
    longitude: Optional[Decimal] = None
    radius_meters: Optional[int] = None
    address: Optional[str] = None
    is_active: Optional[bool] = None

class GeofenceLocationSchema(GeofenceLocationBase):
    uuid: UUID4
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

class GeofenceLocationListResponse(PaginatedResponse[List[GeofenceLocationSchema]]):
    pass

class GeofenceLocationResponse(BaseModel):
    success: bool
    message: str
    data: Optional[GeofenceLocationSchema] = None

class GeofenceValidationRequest(BaseModel):
    latitude: Decimal
    longitude: Decimal
    location_uuid: Optional[UUID4] = None

class GeofenceValidationResult(BaseModel):
    is_within_geofence: bool
    distance_meters: float
    geofence_name: Optional[str] = None
    geofence_uuid: Optional[UUID4] = None

class GeofenceValidationResponse(BaseModel):
    success: bool
    message: str
    data: GeofenceValidationResult

# Approval Delegation Schemas
class ApprovalDelegationBase(BaseModel):
    delegator_uuid: Optional[UUID4] = None
    delegate_to_uuid: Optional[UUID4] = None
    from_date: date
    to_date: date
    delegation_type: DelegationType
    reason: Optional[str] = None
    is_active: bool = True

class ApprovalDelegationCreate(ApprovalDelegationBase):
    delegator_uuid: UUID4
    delegate_to_uuid: UUID4

class ApprovalDelegationUpdate(BaseModel):
    delegate_to_uuid: Optional[UUID4] = None
    from_date: Optional[date] = None
    to_date: Optional[date] = None
    delegation_type: Optional[DelegationType] = None
    reason: Optional[str] = None
    is_active: Optional[bool] = None

class ApprovalDelegationSchema(ApprovalDelegationBase):
    uuid: UUID4
    created_at: datetime
    updated_at: datetime
    delegator_name: Optional[str] = None
    delegate_to_name: Optional[str] = None
    delegator: Optional[EmployeeMinimalSchema] = None
    delegate_to: Optional[EmployeeMinimalSchema] = None

    class Config:
        from_attributes = True

class ApprovalDelegationListResponse(PaginatedResponse[List[ApprovalDelegationSchema]]):
    pass

class ApprovalDelegationResponse(BaseModel):
    success: bool
    message: str
    data: Optional[ApprovalDelegationSchema] = None

# Attendance Bulk Import Schemas
class AttendanceImportError(BaseModel):
    row: int
    error: str
    data: Optional[Any] = None

class AttendanceImportResponse(BaseModel):
    success: bool
    message: str
    success_count: int
    error_count: int
    errors: List[AttendanceImportError] = []

# Payroll Export Schemas
class PayrollExportRequest(BaseModel):
    from_date: date
    to_date: date
    department_uuid: Optional[UUID4] = None

class EmployeePayrollAttendance(BaseModel):
    employee_uuid: UUID4
    employee_code: Optional[str]
    employee_name: str
    total_days: int
    present_days: float
    absent_days: float
    half_days: int
    leave_days: float
    holiday_days: int
    overtime_hours: float
    late_minutes: int
    early_departure_minutes: int
    net_work_hours: float

class PayrollExportResponse(BaseModel):
    success: bool
    message: str
    data: List[EmployeePayrollAttendance]

# Biometric Device Schemas
class BiometricDeviceSchema(BaseModel):
    uuid: UUID4
    device_id: str
    device_name: str
    device_model: Optional[str] = None
    manufacturer: Optional[str] = None
    ip_address: Optional[str] = None
    mac_address: Optional[str] = None
    location_uuid: Optional[UUID4] = None
    physical_location: Optional[str] = None
    connection_type: Optional[str] = None
    is_online: bool
    last_sync_at: Optional[datetime] = None
    last_sync_status: Optional[str] = None
    is_active: bool

    class Config:
        from_attributes = True

class BiometricDeviceListResponse(BaseModel):
    success: bool
    message: str
    data: List[BiometricDeviceSchema]
    pagination: Optional[PaginationData] = None

class BiometricDeviceCreate(BaseModel):
    device_id: str
    device_name: str
    device_model: Optional[str] = None
    manufacturer: Optional[str] = None
    location_uuid: Optional[UUID4] = None
    physical_location: Optional[str] = None
    ip_address: Optional[str] = None
    mac_address: Optional[str] = None
    port: Optional[int] = None
    connection_type: Optional[str] = 'tcp'
    api_endpoint: Optional[str] = None
    username: Optional[str] = None
    password: Optional[str] = None
    api_key: Optional[str] = None
    sync_enabled: bool = True
    sync_frequency_minutes: int = 15
    notes: Optional[str] = None

class BiometricDeviceUpdate(BaseModel):
    device_name: Optional[str] = None
    device_model: Optional[str] = None
    manufacturer: Optional[str] = None
    location_uuid: Optional[UUID4] = None
    physical_location: Optional[str] = None
    ip_address: Optional[str] = None
    mac_address: Optional[str] = None
    port: Optional[int] = None
    sync_enabled: Optional[bool] = None
    sync_frequency_minutes: Optional[int] = None
    is_active: Optional[bool] = None
    notes: Optional[str] = None

class BiometricDeviceResponse(BaseModel):
    success: bool
    message: str
    data: Optional[BiometricDeviceSchema] = None

class BiometricDeviceStatus(BaseModel):
    device_id: str
    is_online: bool
    last_sync_at: Optional[datetime] = None
    last_sync_status: Optional[str] = None
    last_heartbeat: Optional[datetime] = None

class BiometricDeviceStatusResponse(BaseModel):
    success: bool
    message: str
    data: BiometricDeviceStatus
