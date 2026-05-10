from sqlalchemy import Column, Integer, String, Boolean, DateTime, Text, Enum, Date, Time, Numeric, ForeignKey, Index, JSON
from sqlalchemy.orm import relationship
from datetime import datetime
import uuid
import enum
from app.db.base_class import Base
from app.models.organization import GUID

# ============================================================================
# ENUMS
# ============================================================================

class AttendanceStatus(str, enum.Enum):
    PRESENT = "present"
    ABSENT = "absent"
    HALF_DAY = "half_day"
    ON_LEAVE = "on_leave"
    WEEKEND = "weekend"
    HOLIDAY = "holiday"
    WORK_FROM_HOME = "work_from_home"
    ON_DUTY = "on_duty"

class CheckType(str, enum.Enum):
    CHECK_IN = "check_in"
    CHECK_OUT = "check_out"
    BREAK_START = "break_start"
    BREAK_END = "break_end"

class AttendanceSource(str, enum.Enum):
    BIOMETRIC = "biometric"
    WEB = "web"
    MOBILE = "mobile"
    MANUAL = "manual"
    ACCESS_CONTROL = "access_control"
    IMPORTED = "imported"

class RegularizationStatus(str, enum.Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    CANCELLED = "cancelled"

class ShiftType(str, enum.Enum):
    FIXED = "fixed"
    ROTATING = "rotating"
    FLEXIBLE = "flexible"
    SPLIT = "split"
    NIGHT = "night"

class OvertimeStatus(str, enum.Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    PAID = "paid"
    COMP_OFF = "comp_off"

class CompensationType(str, enum.Enum):
    paid = "paid"
    comp_off = "comp_off"
    both = "both"

class DelegationType(str, enum.Enum):
    LEAVE_APPROVAL = "leave_approval"
    ATTENDANCE_APPROVAL = "attendance_approval"
    ALL = "all"

class LeaveStatus(str, enum.Enum):
    DRAFT = "draft"
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    CANCELLED = "cancelled"
    WITHDRAWN = "withdrawn"

class LeaveAccrualType(str, enum.Enum):
    MONTHLY = "monthly"
    YEARLY = "yearly"
    QUARTERLY = "quarterly"
    JOINING_DATE = "joining_date"
    CALENDAR_YEAR = "calendar_year"
    FINANCIAL_YEAR = "financial_year"

class LeaveUnitType(str, enum.Enum):
    FULL_DAY = "full_day"
    HALF_DAY = "half_day"
    HOURLY = "hourly"

class HolidayType(str, enum.Enum):
    PUBLIC = "public"
    RESTRICTED = "restricted"
    OPTIONAL = "optional"
    FLOATING = "floating"

class TimesheetStatus(str, enum.Enum):
    DRAFT = "draft"
    SUBMITTED = "submitted"
    APPROVED = "approved"
    REJECTED = "rejected"

class LeaveEncashmentStatus(str, enum.Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    PAID = "paid"


# ============================================================================
# ATTENDANCE - SHIFT MANAGEMENT
# ============================================================================

class ShiftMaster(Base):
    """Master shift definitions"""
    __tablename__ = "shift_master"
    
    id = Column(Integer, primary_key=True, index=True)
    uuid = Column(GUID(as_uuid=True), default=uuid.uuid4, unique=True, nullable=False, index=True)
    organization_id = Column(Integer, ForeignKey('organization.id'), nullable=False, index=True)
    
    shift_code = Column(String(50), nullable=False, index=True)
    shift_name = Column(String(150), nullable=False)
    shift_type = Column(Enum(ShiftType), nullable=False)
    description = Column(Text, nullable=True)
    
    # Shift Timing
    start_time = Column(Time, nullable=False)
    end_time = Column(Time, nullable=False)
    
    # Working Hours
    work_hours = Column(Numeric(4, 2), nullable=False)  # e.g., 8.00, 9.00
    break_hours = Column(Numeric(4, 2), default=0)
    
    # Break Configuration
    has_break = Column(Boolean, default=False)
    break_start_time = Column(Time, nullable=True)
    break_end_time = Column(Time, nullable=True)
    break_duration_minutes = Column(Integer, nullable=True)
    
    # Grace Period
    late_arrival_grace_minutes = Column(Integer, default=0)
    early_departure_grace_minutes = Column(Integer, default=0)
    
    # Overtime Settings
    overtime_applicable = Column(Boolean, default=True)
    overtime_threshold_minutes = Column(Integer, default=0)  # Minutes after shift end
    
    # Half Day Settings
    half_day_hours = Column(Numeric(4, 2), nullable=True)
    
    # Week-off Configuration
    week_off_days = Column(JSON, nullable=True)  # [0=Sunday, 1=Monday, ...]
    
    # Split Shift (if applicable)
    is_split_shift = Column(Boolean, default=False)
    split_start_time = Column(Time, nullable=True)
    split_end_time = Column(Time, nullable=True)
    
    # Night Shift
    is_night_shift = Column(Boolean, default=False)
    night_shift_allowance = Column(Numeric(10, 2), nullable=True)
    
    # Color Coding (for UI)
    color_code = Column(String(20), nullable=True)
    
    is_active = Column(Boolean, default=True, index=True)
    is_default = Column(Boolean, default=False)
    
    # Audit Fields
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    created_by = Column(Integer, ForeignKey('employees.id'), nullable=True)
    
    # Soft Delete
    is_deleted = Column(Boolean, default=False, nullable=False)
    deleted_at = Column(DateTime, nullable=True)
    
    __table_args__ = (
        Index('idx_shift_org_code', 'organization_id', 'shift_code', unique=True),
    )


# ============================================================================
# LEAVE - LEAVE BALANCE & ACCRUAL
# ============================================================================

class LeaveBalance(Base):
    """Employee leave balances"""
    __tablename__ = "leave_balances"
    
    id = Column(Integer, primary_key=True, index=True)
    uuid = Column(GUID(as_uuid=True), default=uuid.uuid4, unique=True, nullable=False, index=True)
    organization_id = Column(Integer, ForeignKey('organization.id'), nullable=False, index=True)
    
    employee_id = Column(Integer, ForeignKey('employees.id'), nullable=False, index=True)
    leave_type_id = Column(Integer, ForeignKey('leave_types.id'), nullable=False, index=True)
    
    # Balance Period (Year)
    balance_year = Column(Integer, nullable=False, index=True)
    period_start_date = Column(Date, nullable=False)
    period_end_date = Column(Date, nullable=False)
    
    # Opening Balance
    opening_balance = Column(Numeric(6, 2), default=0)
    brought_forward = Column(Numeric(6, 2), default=0)
    
    # Accruals
    accrued = Column(Numeric(6, 2), default=0)
    credited = Column(Numeric(6, 2), default=0)  # Manual credits
    
    # Usage
    used = Column(Numeric(6, 2), default=0)
    pending_approval = Column(Numeric(6, 2), default=0)
    
    # Adjustments
    adjusted = Column(Numeric(6, 2), default=0)
    encashed = Column(Numeric(6, 2), default=0)
    lapsed = Column(Numeric(6, 2), default=0)
    
    # Current Balance
    available_balance = Column(Numeric(6, 2), default=0)
    total_balance = Column(Numeric(6, 2), default=0)
    
    # Carry Forward
    carry_forward_to_next_year = Column(Numeric(6, 2), default=0)
    
    # Last Accrual
    last_accrual_date = Column(Date, nullable=True)
    next_accrual_date = Column(Date, nullable=True)
    
    # Audit Fields
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    employee = relationship("Employee", foreign_keys=[employee_id])
    leave_type = relationship("LeaveType")
    
    __table_args__ = (
        Index('idx_balance_emp_type_year', 'employee_id', 'leave_type_id', 'balance_year', unique=True),
        Index('idx_balance_org_year', 'organization_id', 'balance_year'),
    )


class LeaveAccrualHistory(Base):
    """Track leave accrual transactions"""
    __tablename__ = "leave_accrual_history"
    
    id = Column(Integer, primary_key=True, index=True)
    uuid = Column(GUID(as_uuid=True), default=uuid.uuid4, unique=True, nullable=False)
    
    employee_id = Column(Integer, ForeignKey('employees.id'), nullable=False, index=True)
    leave_type_id = Column(Integer, ForeignKey('leave_types.id'), nullable=False, index=True)
    leave_balance_id = Column(Integer, ForeignKey('leave_balances.id'), nullable=False)
    
    # Accrual Details
    accrual_date = Column(Date, nullable=False, index=True)
    accrual_period = Column(String(50), nullable=True)  # 'Jan-2024', 'Q1-2024'
    accrued_days = Column(Numeric(5, 2), nullable=False)
    
    # Transaction Type
    transaction_type = Column(String(50), nullable=False)  # 'monthly_accrual', 'yearly_credit', 'manual_credit', 'carry_forward'
    
    # Reference
    reference_id = Column(Integer, nullable=True)
    reference_type = Column(String(50), nullable=True)
    
    remarks = Column(Text, nullable=True)
    
    # Balance After Transaction
    balance_after = Column(Numeric(6, 2), nullable=True)
    
    created_at = Column(DateTime, default=datetime.utcnow)
    created_by = Column(Integer, ForeignKey('employees.id'), nullable=True)

    # Relationships
    employee = relationship("Employee", foreign_keys=[employee_id])
    leave_type = relationship("LeaveType")
    leave_balance = relationship("LeaveBalance")


# ============================================================================
# LEAVE - LEAVE APPLICATIONS
# ============================================================================

class LeaveApplication(Base):
    """Leave applications"""
    __tablename__ = "leave_applications"
    
    id = Column(Integer, primary_key=True, index=True)
    uuid = Column(GUID(as_uuid=True), default=uuid.uuid4, unique=True, nullable=False, index=True)
    organization_id = Column(Integer, ForeignKey('organization.id'), nullable=False, index=True)
    
    employee_id = Column(Integer, ForeignKey('employees.id'), nullable=False, index=True)
    leave_type_id = Column(Integer, ForeignKey('leave_types.id'), nullable=False, index=True)
    
    # Application Details
    application_number = Column(String(50), nullable=False, unique=True, index=True)
    application_date = Column(Date, default=datetime.utcnow, nullable=False)
    
    # Leave Period
    from_date = Column(Date, nullable=False, index=True)
    to_date = Column(Date, nullable=False, index=True)
    
    # Duration
    total_days = Column(Numeric(5, 2), nullable=False)
    is_half_day = Column(Boolean, default=False)
    half_day_session = Column(String(20), nullable=True)  # 'first_half', 'second_half'
    
    # Reason
    reason = Column(Text, nullable=False)
    reason_category = Column(String(50), nullable=True)
    
    # Contact Information
    contact_address = Column(Text, nullable=True)
    contact_phone = Column(String(20), nullable=True)
    
    # Supporting Documents
    attachment_urls = Column(JSON, nullable=True)
    
    # Status
    status = Column(Enum(LeaveStatus), default=LeaveStatus.PENDING, nullable=False, index=True)
    
    # Approval Workflow
    current_approver_id = Column(Integer, ForeignKey('employees.id'), nullable=True, index=True)
    approval_level = Column(Integer, default=0)
    
    # Final Approval/Rejection
    approved_by = Column(Integer, ForeignKey('employees.id'), nullable=True)
    approved_at = Column(DateTime, nullable=True)
    rejection_reason = Column(Text, nullable=True)
    rejected_by = Column(Integer, ForeignKey('employees.id'), nullable=True)
    rejected_at = Column(DateTime, nullable=True)
    
    # Cancellation/Withdrawal
    cancelled_at = Column(DateTime, nullable=True)
    cancellation_reason = Column(Text, nullable=True)
    
    # Balance Deduction
    balance_deducted = Column(Boolean, default=False)
    deducted_from_balance_id = Column(Integer, ForeignKey('leave_balances.id'), nullable=True)
    
    # Comp-off Utilization
    is_comp_off = Column(Boolean, default=False)
    comp_off_id = Column(Integer, ForeignKey('compensatory_offs.id'), nullable=True)
    
    # Payroll Integration
    payroll_processed = Column(Boolean, default=False)
    payroll_period_id = Column(Integer, nullable=True)
    
    # Delegation (if manager is on leave)
    delegated_approver_id = Column(Integer, ForeignKey('employees.id'), nullable=True)
    
    # Remarks
    remarks = Column(Text, nullable=True)
    approver_comments = Column(Text, nullable=True)
    
    # Audit Fields
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    __table_args__ = (
        Index('idx_leave_app_emp_dates', 'employee_id', 'from_date', 'to_date'),
        Index('idx_leave_app_status', 'organization_id', 'status'),
        Index('idx_leave_app_approver', 'current_approver_id', 'status'),
        Index('idx_leave_app_emp_status_dates', 'employee_id', 'status', 'from_date', 'to_date'),
    )
    
    # Relationships
    employee = relationship("Employee", foreign_keys=[employee_id])
    leave_type = relationship("LeaveType")
    current_approver = relationship("Employee", foreign_keys=[current_approver_id])
    approved_by_user = relationship("Employee", foreign_keys=[approved_by])
    rejected_by_user = relationship("Employee", foreign_keys=[rejected_by])
    leave_balance = relationship("LeaveBalance", foreign_keys=[deducted_from_balance_id])
    approval_history = relationship("LeaveApprovalHistory", back_populates="application")


class LeaveApprovalHistory(Base):
    """Leave approval workflow history"""
    __tablename__ = "leave_approval_history"
    
    id = Column(Integer, primary_key=True, index=True)
    leave_application_id = Column(Integer, ForeignKey('leave_applications.id'), nullable=False, index=True)
    
    approval_level = Column(Integer, nullable=False)
    approver_id = Column(Integer, ForeignKey('employees.id'), nullable=False, index=True)
    
    action = Column(String(20), nullable=False)  # 'approved', 'rejected', 'delegated'
    action_date = Column(DateTime, default=datetime.utcnow, nullable=False)
    
    comments = Column(Text, nullable=True)
    
    # Relationships
    application = relationship("LeaveApplication", back_populates="approval_history")
    approver = relationship("Employee", foreign_keys=[approver_id])
    
    # Delegation
    delegated_to_id = Column(Integer, ForeignKey('employees.id'), nullable=True)
    delegation_reason = Column(Text, nullable=True)
    
    created_at = Column(DateTime, default=datetime.utcnow)


# ============================================================================
# LEAVE - COMPENSATORY OFF
# ============================================================================

class CompensatoryOff(Base):
    """Compensatory off credits and utilization"""
    __tablename__ = "compensatory_offs"
    
    id = Column(Integer, primary_key=True, index=True)
    uuid = Column(GUID(as_uuid=True), default=uuid.uuid4, unique=True, nullable=False, index=True)
    organization_id = Column(Integer, ForeignKey('organization.id'), nullable=False, index=True)
    
    employee_id = Column(Integer, ForeignKey('employees.id'), nullable=False, index=True)
    
    # Credit Details
    worked_date = Column(Date, nullable=False, index=True)
    comp_off_days = Column(Numeric(4, 2), nullable=False)
    
    # Source
    source_type = Column(String(50), nullable=False)  # 'weekend_work', 'holiday_work', 'overtime'
    source_reference_id = Column(Integer, nullable=True)  # overtime_request_id or attendance_record_id
    
    # Reason for Work
    reason = Column(Text, nullable=True)
    
    # Approval
    approved_by = Column(Integer, ForeignKey('employees.id'), nullable=True)
    approved_at = Column(DateTime, nullable=True)
    
    # Validity
    credited_date = Column(Date, nullable=False)
    expiry_date = Column(Date, nullable=False, index=True)
    
    # Utilization
    is_utilized = Column(Boolean, default=False, index=True)
    utilized_days = Column(Numeric(4, 2), default=0)
    remaining_days = Column(Numeric(4, 2), nullable=False)
    
    # Leave Application Reference
    leave_application_id = Column(Integer, ForeignKey('leave_applications.id'), nullable=True)
    utilized_date = Column(Date, nullable=True)
    
    # Expiry/Lapse
    is_expired = Column(Boolean, default=False)
    is_lapsed = Column(Boolean, default=False)
    lapsed_days = Column(Numeric(4, 2), default=0)
    
    # Audit Fields
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    __table_args__ = (
        Index('idx_compoff_emp_expiry', 'employee_id', 'is_utilized', 'expiry_date'),
    )

    # Relationships
    employee = relationship("Employee", foreign_keys=[employee_id])
    leave_application = relationship("LeaveApplication", foreign_keys=[leave_application_id])


# ============================================================================
# LEAVE - HOLIDAYS
# ============================================================================

class Holiday(Base):
    """Holiday calendar"""
    __tablename__ = "holidays"
    
    id = Column(Integer, primary_key=True, index=True)
    uuid = Column(GUID(as_uuid=True), default=uuid.uuid4, unique=True, nullable=False, index=True)
    organization_id = Column(Integer, ForeignKey('organization.id'), nullable=False, index=True)
    
    holiday_name = Column(String(200), nullable=False)
    holiday_date = Column(Date, nullable=False, index=True)
    holiday_type = Column(Enum(HolidayType), nullable=False)
    
    description = Column(Text, nullable=True)
    
    # Location Specific
    is_location_specific = Column(Boolean, default=False)
    location_ids = Column(JSON, nullable=True)
    
    # Department Specific
    is_department_specific = Column(Boolean, default=False)
    department_ids = Column(JSON, nullable=True)
    
    # Optional Holiday Management
    is_optional = Column(Boolean, default=False)
    optional_quota_required = Column(Boolean, default=False)
    
    # Restricted Holiday (limited availability)
    is_restricted = Column(Boolean, default=False)
    max_employees_allowed = Column(Integer, nullable=True)
    employees_applied = Column(Integer, default=0)
    
    # Year
    holiday_year = Column(Integer, nullable=False, index=True)
    
    is_active = Column(Boolean, default=True)
    
    # Audit Fields
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    created_by = Column(Integer, ForeignKey('employees.id'), nullable=True)
    is_deleted = Column(Boolean, default=False, index=True)
    deleted_at = Column(DateTime, nullable=True)
    
    __table_args__ = (
        Index('idx_holiday_org_date', 'organization_id', 'holiday_date'),
        Index('idx_holiday_year', 'organization_id', 'holiday_year'),
    )


class OptionalHolidaySelection(Base):
    """Employee selections for optional holidays"""
    __tablename__ = "optional_holiday_selections"
    
    id = Column(Integer, primary_key=True, index=True)
    employee_id = Column(Integer, ForeignKey('employees.id'), nullable=False, index=True)
    holiday_id = Column(Integer, ForeignKey('holidays.id'), nullable=False, index=True)
    
    selection_year = Column(Integer, nullable=False)
    selected_at = Column(DateTime, default=datetime.utcnow)
    
    # Usage
    is_availed = Column(Boolean, default=False)
    availed_date = Column(Date, nullable=True)
    
    created_at = Column(DateTime, default=datetime.utcnow)
    
    __table_args__ = (
        Index('idx_optional_emp_holiday', 'employee_id', 'holiday_id', unique=True),
    )

    # Relationships
    employee = relationship("Employee", foreign_keys=[employee_id])
    holiday = relationship("Holiday", foreign_keys=[holiday_id])


# ============================================================================
# LEAVE - ENCASHMENT
# ============================================================================

class LeaveEncashment(Base):
    """Leave encashment requests and processing"""
    __tablename__ = "leave_encashments"
    
    id = Column(Integer, primary_key=True, index=True)
    uuid = Column(GUID(as_uuid=True), default=uuid.uuid4, unique=True, nullable=False, index=True)
    organization_id = Column(Integer, ForeignKey('organization.id'), nullable=False, index=True)
    
    employee_id = Column(Integer, ForeignKey('employees.id'), nullable=False, index=True)
    leave_type_id = Column(Integer, ForeignKey('leave_types.id'), nullable=False, index=True)
    
    # Encashment Details
    encashment_number = Column(String(50), nullable=False, unique=True, index=True)
    encashment_date = Column(Date, default=datetime.utcnow, nullable=False)
    
    # Leave Balance
    leave_balance_id = Column(Integer, ForeignKey('leave_balances.id'), nullable=False)
    available_days = Column(Numeric(6, 2), nullable=False)
    encashment_days = Column(Numeric(6, 2), nullable=False)
    
    # Financial Details
    per_day_salary = Column(Numeric(12, 2), nullable=False)
    encashment_amount = Column(Numeric(12, 2), nullable=False)
    
    # Tax Implications
    is_taxable = Column(Boolean, default=True)
    tax_deducted = Column(Numeric(12, 2), default=0)
    net_amount = Column(Numeric(12, 2), nullable=False)
    
    # Approval
    status = Column(Enum(LeaveEncashmentStatus), default=LeaveEncashmentStatus.PENDING, nullable=False, index=True)
    approved_by = Column(Integer, ForeignKey('employees.id'), nullable=True)
    approved_at = Column(DateTime, nullable=True)
    rejection_reason = Column(Text, nullable=True)
    
    # Payment Processing
    is_paid = Column(Boolean, default=False)
    payment_date = Column(Date, nullable=True)
    payroll_period_id = Column(Integer, nullable=True)
    payment_reference = Column(String(100), nullable=True)
    
    remarks = Column(Text, nullable=True)
    
    # Audit Fields
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    __table_args__ = (
        Index('idx_encash_emp_date', 'employee_id', 'encashment_date'),
    )

    # Relationships
    employee = relationship("Employee", foreign_keys=[employee_id])
    leave_type = relationship("LeaveType", foreign_keys=[leave_type_id])
    approved_by_user = relationship("Employee", foreign_keys=[approved_by])


# ============================================================================
# ATTENDANCE - GEOFENCING
# ============================================================================

class GeofenceLocation(Base):
    """Geofence definitions for location-based attendance"""
    __tablename__ = "geofence_locations"
    
    id = Column(Integer, primary_key=True, index=True)
    uuid = Column(GUID(as_uuid=True), default=uuid.uuid4, unique=True, nullable=False)
    organization_id = Column(Integer, ForeignKey('organization.id'), nullable=False, index=True)
    
    location_name = Column(String(150), nullable=False)
    location_id = Column(Integer, ForeignKey('locations.id'), nullable=True)
    
    # Center Point
    latitude = Column(Numeric(10, 8), nullable=False)
    longitude = Column(Numeric(11, 8), nullable=False)
    
    # Radius (in meters)
    radius_meters = Column(Integer, nullable=False)
    
    # Address
    address = Column(Text, nullable=True)
    
    is_active = Column(Boolean, default=True)
    
    # Audit Fields
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    created_by = Column(Integer, ForeignKey('employees.id'), nullable=True)

    # Soft Delete
    is_deleted = Column(Boolean, default=False, index=True)
    deleted_at = Column(DateTime, nullable=True)


# ============================================================================
# ATTENDANCE - POLICIES & RULES
# ============================================================================

class AttendancePolicy(Base):
    """Attendance policies and rules"""
    __tablename__ = "attendance_policies"
    
    id = Column(Integer, primary_key=True, index=True)
    uuid = Column(GUID(as_uuid=True), default=uuid.uuid4, unique=True, nullable=False)
    organization_id = Column(Integer, ForeignKey('organization.id'), nullable=False, index=True)
    
    policy_name = Column(String(150), nullable=False)
    description = Column(Text, nullable=True)
    
    # Working Days
    working_days_per_week = Column(Integer, default=5)
    working_hours_per_day = Column(Numeric(4, 2), default=8.00)
    working_hours_per_week = Column(Numeric(5, 2), default=40.00)
    
    # Grace Periods (in minutes)
    late_arrival_grace = Column(Integer, default=0)
    early_departure_grace = Column(Integer, default=0)
    
    # Break Rules
    break_duration_minutes = Column(Integer, default=60)
    is_break_mandatory = Column(Boolean, default=False)
    max_break_duration_minutes = Column(Integer, nullable=True)
    
    # Half Day Rules
    half_day_threshold_hours = Column(Numeric(4, 2), default=4.00)
    
    # Absent Rules
    absent_threshold_hours = Column(Numeric(4, 2), default=0.00)  # Below this = absent
    
    # Overtime Rules
    overtime_enabled = Column(Boolean, default=True)
    overtime_threshold_minutes = Column(Integer, default=0)
    overtime_multiplier = Column(Numeric(4, 2), default=1.5)
    max_overtime_hours_per_day = Column(Numeric(4, 2), nullable=True)
    max_overtime_hours_per_month = Column(Numeric(6, 2), nullable=True)
    
    # Regularization Rules
    regularization_allowed = Column(Boolean, default=True)
    max_regularizations_per_month = Column(Integer, default=3)
    regularization_approval_required = Column(Boolean, default=True)
    
    # Late/Early Penalties
    late_deduction_enabled = Column(Boolean, default=False)
    late_deduction_after_minutes = Column(Integer, default=15)
    late_deduction_per_occurrence = Column(Numeric(6, 2), nullable=True)
    
    # Applicability
    applicable_to = Column(String(50), nullable=True)  # 'all', 'department', 'location'
    department_ids = Column(JSON, nullable=True)
    location_ids = Column(JSON, nullable=True)
    employment_types = Column(JSON, nullable=True)
    
    # Effective Dates
    effective_from = Column(Date, nullable=False)
    effective_to = Column(Date, nullable=True)
    
    is_active = Column(Boolean, default=True)
    is_default = Column(Boolean, default=False)
    
    # Audit Fields
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    created_by = Column(Integer, ForeignKey('employees.id'), nullable=True)
    
    # Soft Delete
    is_deleted = Column(Boolean, default=False, index=True)
    deleted_at = Column(DateTime, nullable=True)


# ============================================================================
# LEAVE - DELEGATION
# ============================================================================

class ApprovalDelegation(Base):
    """Delegate approval authority when manager is on leave"""
    __tablename__ = "approval_delegations"
    
    id = Column(Integer, primary_key=True, index=True)
    uuid = Column(GUID(as_uuid=True), default=uuid.uuid4, unique=True, nullable=False)
    organization_id = Column(Integer, ForeignKey('organization.id'), nullable=False, index=True)
    
    delegator_id = Column(Integer, ForeignKey('employees.id'), nullable=False, index=True)
    delegate_to_id = Column(Integer, ForeignKey('employees.id'), nullable=False, index=True)
    
    # Delegation Period
    from_date = Column(Date, nullable=False, index=True)
    to_date = Column(Date, nullable=False, index=True)
    
    # Delegation Type
    delegation_type = Column(Enum(DelegationType), nullable=False, default=DelegationType.ALL)
    
    # Reason
    reason = Column(Text, nullable=True)
    
    is_active = Column(Boolean, default=True, index=True)
    
    # Audit Fields
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    __table_args__ = (
        Index('idx_delegation_dates', 'delegator_id', 'from_date', 'to_date'),
    )
    
    # Relationships
    delegator = relationship("Employee", foreign_keys=[delegator_id])
    delegate_to = relationship("Employee", foreign_keys=[delegate_to_id])


# ============================================================================
# ANALYTICS & REPORTING
# ============================================================================

class AttendanceMetrics(Base):
    """Store attendance KPIs and metrics"""
    __tablename__ = "attendance_metrics"
    
    id = Column(Integer, primary_key=True, index=True)
    organization_id = Column(Integer, ForeignKey('organization.id'), nullable=False, index=True)
    
    metric_date = Column(Date, nullable=False, index=True)
    metric_type = Column(String(50), nullable=False)  # 'daily', 'weekly', 'monthly'
    
    # Department/Location (optional for aggregation)
    department_id = Column(Integer, ForeignKey('departments.id'), nullable=True)
    location_id = Column(Integer, ForeignKey('locations.id'), nullable=True)
    
    # Attendance Metrics
    total_employees = Column(Integer, default=0)
    present_count = Column(Integer, default=0)
    absent_count = Column(Integer, default=0)
    on_leave_count = Column(Integer, default=0)
    half_day_count = Column(Integer, default=0)
    wfh_count = Column(Integer, default=0)
    
    # Punctuality
    late_arrivals = Column(Integer, default=0)
    early_departures = Column(Integer, default=0)
    
    # Percentages
    attendance_percentage = Column(Numeric(5, 2), nullable=True)
    absence_rate = Column(Numeric(5, 2), nullable=True)
    
    # Working Hours
    total_work_hours = Column(Numeric(10, 2), default=0)
    avg_work_hours_per_employee = Column(Numeric(5, 2), nullable=True)
    total_overtime_hours = Column(Numeric(8, 2), default=0)
    
    # Regularizations
    regularization_requests = Column(Integer, default=0)
    
    created_at = Column(DateTime, default=datetime.utcnow)
    
    __table_args__ = (
        Index('idx_att_metrics_org_date', 'organization_id', 'metric_date'),
    )


class LeaveMetrics(Base):
    """Store leave KPIs and metrics"""
    __tablename__ = "leave_metrics"
    
    id = Column(Integer, primary_key=True, index=True)
    organization_id = Column(Integer, ForeignKey('organization.id'), nullable=False, index=True)
    
    metric_date = Column(Date, nullable=False, index=True)
    metric_type = Column(String(50), nullable=False)  # 'daily', 'monthly', 'yearly'
    
    # Department/Location (optional)
    department_id = Column(Integer, ForeignKey('departments.id'), nullable=True)
    location_id = Column(Integer, ForeignKey('locations.id'), nullable=True)
    leave_type_id = Column(Integer, ForeignKey('leave_types.id'), nullable=True)
    
    # Application Metrics
    total_applications = Column(Integer, default=0)
    pending_applications = Column(Integer, default=0)
    approved_applications = Column(Integer, default=0)
    rejected_applications = Column(Integer, default=0)
    
    # Leave Days
    total_leave_days = Column(Numeric(8, 2), default=0)
    planned_leaves = Column(Numeric(8, 2), default=0)
    unplanned_leaves = Column(Numeric(8, 2), default=0)
    
    # Averages
    avg_approval_time_hours = Column(Numeric(6, 2), nullable=True)
    avg_leave_duration_days = Column(Numeric(4, 2), nullable=True)
    
    # Trends
    leave_utilization_rate = Column(Numeric(5, 2), nullable=True)
    
    created_at = Column(DateTime, default=datetime.utcnow)
    
    __table_args__ = (
        Index('idx_leave_metrics_org_date', 'organization_id', 'metric_date'),
    )


# ============================================================================
# NOTIFICATIONS & REMINDERS
# ============================================================================

class AttendanceNotification(Base):
    """Notifications for attendance and leave"""
    __tablename__ = "attendance_notifications"
    
    id = Column(Integer, primary_key=True, index=True)
    uuid = Column(GUID(as_uuid=True), default=uuid.uuid4, unique=True, nullable=False)
    organization_id = Column(Integer, ForeignKey('organization.id'), nullable=False, index=True)
    
    employee_id = Column(Integer, ForeignKey('employees.id'), nullable=False, index=True)
    
    # Notification Details
    notification_type = Column(String(50), nullable=False, index=True)  
    # 'leave_approved', 'leave_rejected', 'regularization_pending', 'overtime_approved', 'leave_balance_low'
    
    title = Column(String(255), nullable=False)
    message = Column(Text, nullable=False)
    
    # Reference
    reference_type = Column(String(50), nullable=True)  # 'leave_application', 'attendance_regularization'
    reference_id = Column(Integer, nullable=True)
    
    # Delivery Channels
    send_email = Column(Boolean, default=True)
    send_push = Column(Boolean, default=True)
    send_sms = Column(Boolean, default=False)
    
    # Status
    is_sent = Column(Boolean, default=False, index=True)
    sent_at = Column(DateTime, nullable=True)
    
    is_read = Column(Boolean, default=False)
    read_at = Column(DateTime, nullable=True)
    
    # Priority
    priority = Column(String(20), default='normal')  # 'low', 'normal', 'high', 'urgent'
    
    created_at = Column(DateTime, default=datetime.utcnow)
    
    __table_args__ = (
        Index('idx_notif_emp_sent', 'employee_id', 'is_sent', 'created_at'),
    )


# ============================================================================
# BIOMETRIC DEVICE MANAGEMENT
# ============================================================================

class BiometricDevice(Base):
    """Biometric devices for attendance capture"""
    __tablename__ = "biometric_devices"
    
    id = Column(Integer, primary_key=True, index=True)
    uuid = Column(GUID(as_uuid=True), default=uuid.uuid4, unique=True, nullable=False, index=True)
    organization_id = Column(Integer, ForeignKey('organization.id'), nullable=False, index=True)
    
    device_id = Column(String(100), nullable=False, unique=True, index=True)
    device_name = Column(String(150), nullable=False)
    device_model = Column(String(100), nullable=True)
    manufacturer = Column(String(100), nullable=True)
    
    # Location
    location_id = Column(Integer, ForeignKey('locations.id'), nullable=True)
    physical_location = Column(String(255), nullable=True)
    
    # Network Details
    ip_address = Column(String(50), nullable=True)
    mac_address = Column(String(50), nullable=True)
    port = Column(Integer, nullable=True)
    
    # Connection
    connection_type = Column(String(50), nullable=True)  # 'tcp', 'serial', 'usb', 'cloud'
    api_endpoint = Column(String(500), nullable=True)
    
    # Authentication
    username = Column(String(100), nullable=True)
    password = Column(String(255), nullable=True)  # Encrypted
    api_key = Column(String(255), nullable=True)  # Encrypted
    
    # Sync Configuration
    sync_enabled = Column(Boolean, default=True)
    sync_frequency_minutes = Column(Integer, default=15)
    last_sync_at = Column(DateTime, nullable=True)
    last_sync_status = Column(String(50), nullable=True)  # 'success', 'failed', 'partial'
    last_sync_records = Column(Integer, default=0)
    
    # Device Status
    is_online = Column(Boolean, default=False, index=True)
    last_heartbeat = Column(DateTime, nullable=True)
    
    # Capacity
    max_users = Column(Integer, nullable=True)
    max_logs = Column(Integer, nullable=True)
    current_users = Column(Integer, default=0)
    current_logs = Column(Integer, default=0)
    
    # Features
    supports_fingerprint = Column(Boolean, default=True)
    supports_face = Column(Boolean, default=False)
    supports_card = Column(Boolean, default=False)
    supports_pin = Column(Boolean, default=False)
    
    is_active = Column(Boolean, default=True, index=True)
    
    # Notes
    notes = Column(Text, nullable=True)
    
    # Audit Fields
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    created_by = Column(Integer, ForeignKey('employees.id'), nullable=True)


class DeviceSyncLog(Base):
    """Log of device sync operations"""
    __tablename__ = "device_sync_logs"
    
    id = Column(Integer, primary_key=True, index=True)
    device_id = Column(Integer, ForeignKey('biometric_devices.id'), nullable=False, index=True)
    
    sync_started_at = Column(DateTime, nullable=False, index=True)
    sync_completed_at = Column(DateTime, nullable=True)
    
    sync_status = Column(String(50), nullable=False)  # 'success', 'failed', 'partial'
    records_fetched = Column(Integer, default=0)
    records_processed = Column(Integer, default=0)
    records_failed = Column(Integer, default=0)
    
    # Error Information
    error_message = Column(Text, nullable=True)
    error_details = Column(JSON, nullable=True)
    
    # Performance
    duration_seconds = Column(Integer, nullable=True)
    
    created_at = Column(DateTime, default=datetime.utcnow)


# ============================================================================
# EMPLOYEE BIOMETRIC TEMPLATES
# ============================================================================

class EmployeeBiometricTemplate(Base):
    """Store biometric template references for employees"""
    __tablename__ = "employee_biometric_templates"
    
    id = Column(Integer, primary_key=True, index=True)
    uuid = Column(GUID(as_uuid=True), default=uuid.uuid4, unique=True, nullable=False)
    organization_id = Column(Integer, ForeignKey('organization.id'), nullable=False, index=True)
    
    employee_id = Column(Integer, ForeignKey('employees.id'), nullable=False, index=True)
    device_id = Column(Integer, ForeignKey('biometric_devices.id'), nullable=True)
    
    # Biometric Type
    biometric_type = Column(String(50), nullable=False)  # 'fingerprint', 'face', 'iris', 'palm'
    template_index = Column(Integer, nullable=True)  # Finger index for fingerprint
    
    # Template Data (typically stored in device, this is reference)
    template_id = Column(String(100), nullable=True)
    template_quality_score = Column(Integer, nullable=True)
    
    # Enrollment
    enrolled_at = Column(DateTime, default=datetime.utcnow)
    enrolled_by = Column(Integer, ForeignKey('employees.id'), nullable=True)
    
    # Synced to Device
    synced_to_device = Column(Boolean, default=False)
    synced_at = Column(DateTime, nullable=True)
    
    is_active = Column(Boolean, default=True, index=True)
    
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    __table_args__ = (
        Index('idx_bio_emp_type', 'employee_id', 'biometric_type'),
    )


# ============================================================================
# ATTENDANCE EXCEPTIONS & ALERTS
# ============================================================================

class AttendanceException(Base):
    """Track attendance exceptions and anomalies"""
    __tablename__ = "attendance_exceptions"
    
    id = Column(Integer, primary_key=True, index=True)
    uuid = Column(GUID(as_uuid=True), default=uuid.uuid4, unique=True, nullable=False)
    organization_id = Column(Integer, ForeignKey('organization.id'), nullable=False, index=True)
    
    employee_id = Column(Integer, ForeignKey('employees.id'), nullable=False, index=True)
    exception_date = Column(Date, nullable=False, index=True)
    
    # Exception Type
    exception_type = Column(String(50), nullable=False, index=True)
    # 'missing_checkout', 'missing_checkin', 'excessive_hours', 'late_arrival', 
    # 'early_departure', 'absent_without_leave', 'duplicate_punch', 'geofence_violation'
    
    exception_severity = Column(String(20), default='medium')  # 'low', 'medium', 'high', 'critical'
    
    # Details
    exception_description = Column(Text, nullable=True)
    exception_data = Column(JSON, nullable=True)  # Additional context
    
    # Resolution
    is_resolved = Column(Boolean, default=False, index=True)
    resolved_at = Column(DateTime, nullable=True)
    resolved_by = Column(Integer, ForeignKey('employees.id'), nullable=True)
    resolution_notes = Column(Text, nullable=True)
    resolution_action = Column(String(100), nullable=True)  # 'regularized', 'leave_applied', 'ignored'
    
    # Notification
    notification_sent = Column(Boolean, default=False)
    notification_sent_at = Column(DateTime, nullable=True)
    
    # Reference
    attendance_record_id = Column(Integer, ForeignKey('attendance_records.id'), nullable=True)
    
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    __table_args__ = (
        Index('idx_exception_emp_date', 'employee_id', 'exception_date'),
        Index('idx_exception_unresolved', 'is_resolved', 'exception_date'),
    )


class LeaveException(Base):
    """Track leave exceptions and conflicts"""
    __tablename__ = "leave_exceptions"
    
    id = Column(Integer, primary_key=True, index=True)
    uuid = Column(GUID(as_uuid=True), default=uuid.uuid4, unique=True, nullable=False)
    organization_id = Column(Integer, ForeignKey('organization.id'), nullable=False, index=True)
    
    employee_id = Column(Integer, ForeignKey('employees.id'), nullable=False, index=True)
    leave_application_id = Column(Integer, ForeignKey('leave_applications.id'), nullable=True, index=True)
    
    # Exception Type
    exception_type = Column(String(50), nullable=False, index=True)
    # 'insufficient_balance', 'team_conflict', 'blackout_period', 'max_consecutive_exceeded',
    # 'documentation_missing', 'backdated', 'overlapping_leave'
    
    exception_severity = Column(String(20), default='medium')
    exception_description = Column(Text, nullable=True)
    exception_data = Column(JSON, nullable=True)
    
    # Status
    is_override_approved = Column(Boolean, default=False)
    override_approved_by = Column(Integer, ForeignKey('employees.id'), nullable=True)
    override_reason = Column(Text, nullable=True)
    
    created_at = Column(DateTime, default=datetime.utcnow)


# ============================================================================
# WORK FROM HOME (WFH) / ON DUTY
# ============================================================================

class WorkFromHomeRequest(Base):
    """Work from home requests"""
    __tablename__ = "work_from_home_requests"
    
    id = Column(Integer, primary_key=True, index=True)
    uuid = Column(GUID(as_uuid=True), default=uuid.uuid4, unique=True, nullable=False, index=True)
    organization_id = Column(Integer, ForeignKey('organization.id'), nullable=False, index=True)
    
    employee_id = Column(Integer, ForeignKey('employees.id'), nullable=False, index=True)
    
    # Request Details
    from_date = Column(Date, nullable=False, index=True)
    to_date = Column(Date, nullable=False, index=True)
    total_days = Column(Integer, nullable=False)
    
    # Reason
    reason = Column(Text, nullable=False)
    work_plan = Column(Text, nullable=True)
    
    # Status
    status = Column(String(20), default='pending', nullable=False, index=True)
    # 'pending', 'approved', 'rejected', 'cancelled'
    
    # Approval
    approver_id = Column(Integer, ForeignKey('employees.id'), nullable=True, index=True)
    approved_at = Column(DateTime, nullable=True)
    approver_comments = Column(Text, nullable=True)
    
    rejection_reason = Column(Text, nullable=True)
    
    # Attendance Integration
    attendance_marked_as_wfh = Column(Boolean, default=False)
    
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    __table_args__ = (
        Index('idx_wfh_emp_dates', 'employee_id', 'from_date', 'to_date'),
    )


class OnDutyRequest(Base):
    """On duty / field work requests"""
    __tablename__ = "on_duty_requests"
    
    id = Column(Integer, primary_key=True, index=True)
    uuid = Column(GUID(as_uuid=True), default=uuid.uuid4, unique=True, nullable=False, index=True)
    organization_id = Column(Integer, ForeignKey('organization.id'), nullable=False, index=True)
    
    employee_id = Column(Integer, ForeignKey('employees.id'), nullable=False, index=True)
    
    # Request Details
    from_date = Column(Date, nullable=False, index=True)
    to_date = Column(Date, nullable=False, index=True)
    from_time = Column(Time, nullable=True)
    to_time = Column(Time, nullable=True)
    
    # Purpose
    purpose = Column(Text, nullable=False)
    purpose_type = Column(String(50), nullable=True)  # 'client_visit', 'site_visit', 'training', 'meeting'
    
    # Location
    location = Column(String(255), nullable=True)
    client_name = Column(String(200), nullable=True)
    
    # Status
    status = Column(String(20), default='pending', nullable=False, index=True)
    
    # Approval
    approver_id = Column(Integer, ForeignKey('employees.id'), nullable=True, index=True)
    approved_at = Column(DateTime, nullable=True)
    approver_comments = Column(Text, nullable=True)
    
    rejection_reason = Column(Text, nullable=True)
    
    # Attendance Integration
    attendance_marked_as_on_duty = Column(Boolean, default=False)
    
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    __table_args__ = (
        Index('idx_on_duty_emp_dates', 'employee_id', 'from_date', 'to_date'),
    )


# ============================================================================
# LEAVE BLACKOUT PERIODS
# ============================================================================

class LeaveBlackoutPeriod(Base):
    """Define periods when leave cannot be taken"""
    __tablename__ = "leave_blackout_periods"
    
    id = Column(Integer, primary_key=True, index=True)
    uuid = Column(GUID(as_uuid=True), default=uuid.uuid4, unique=True, nullable=False)
    organization_id = Column(Integer, ForeignKey('organization.id'), nullable=False, index=True)
    
    blackout_name = Column(String(150), nullable=False)
    description = Column(Text, nullable=True)
    
    # Period
    from_date = Column(Date, nullable=False, index=True)
    to_date = Column(Date, nullable=False, index=True)
    
    # Applicability
    applies_to_all = Column(Boolean, default=False)
    department_ids = Column(JSON, nullable=True)
    location_ids = Column(JSON, nullable=True)
    
    # Leave Types (which leaves are blocked)
    leave_type_ids = Column(JSON, nullable=True)  # If null, all leaves blocked
    
    # Restrictions
    allow_emergency_leave = Column(Boolean, default=True)
    override_allowed = Column(Boolean, default=False)
    override_approval_required = Column(Boolean, default=True)
    
    is_active = Column(Boolean, default=True)
    
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    created_by = Column(Integer, ForeignKey('employees.id'), nullable=True)


# ============================================================================
# LEAVE QUOTAS & RESTRICTIONS
# ============================================================================

class LeaveQuota(Base):
    """Team/department level leave quotas"""
    __tablename__ = "leave_quotas"
    
    id = Column(Integer, primary_key=True, index=True)
    uuid = Column(GUID(as_uuid=True), default=uuid.uuid4, unique=True, nullable=False)
    organization_id = Column(Integer, ForeignKey('organization.id'), nullable=False, index=True)
    
    quota_name = Column(String(150), nullable=False)
    quota_type = Column(String(50), nullable=False)  # 'daily', 'weekly', 'monthly'
    
    # Applicability
    department_id = Column(Integer, ForeignKey('departments.id'), nullable=True)
    location_id = Column(Integer, ForeignKey('locations.id'), nullable=True)
    team_id = Column(Integer, nullable=True)
    
    # Quota Settings
    max_employees_on_leave = Column(Integer, nullable=False)
    min_employees_present = Column(Integer, nullable=True)
    
    # Leave Types
    leave_type_ids = Column(JSON, nullable=True)  # If null, applies to all
    
    # Effective Period
    effective_from = Column(Date, nullable=False)
    effective_to = Column(Date, nullable=True)
    
    is_active = Column(Boolean, default=True)
    
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    created_by = Column(Integer, ForeignKey('employees.id'), nullable=True)


# ============================================================================
# SHIFT SWAP / EXCHANGE
# ============================================================================

class ShiftSwapRequest(Base):
    """Employee shift swap/exchange requests"""
    __tablename__ = "shift_swap_requests"
    
    id = Column(Integer, primary_key=True, index=True)
    uuid = Column(GUID(as_uuid=True), default=uuid.uuid4, unique=True, nullable=False, index=True)
    organization_id = Column(Integer, ForeignKey('organization.id'), nullable=False, index=True)
    
    # Requester
    requester_employee_id = Column(Integer, ForeignKey('employees.id'), nullable=False, index=True)
    requester_shift_date = Column(Date, nullable=False)
    requester_shift_id = Column(Integer, ForeignKey('shift_master.id'), nullable=False)
    
    # Exchange With
    exchange_employee_id = Column(Integer, ForeignKey('employees.id'), nullable=False, index=True)
    exchange_shift_date = Column(Date, nullable=False)
    exchange_shift_id = Column(Integer, ForeignKey('shift_master.id'), nullable=False)
    
    # Reason
    reason = Column(Text, nullable=False)
    
    # Status
    status = Column(String(20), default='pending', nullable=False, index=True)
    # 'pending', 'accepted_by_peer', 'rejected_by_peer', 'approved_by_manager', 'rejected_by_manager', 'completed'
    
    # Peer Acceptance
    peer_accepted_at = Column(DateTime, nullable=True)
    peer_rejection_reason = Column(Text, nullable=True)
    
    # Manager Approval
    approver_id = Column(Integer, ForeignKey('employees.id'), nullable=True)
    approved_at = Column(DateTime, nullable=True)
    approver_comments = Column(Text, nullable=True)
    manager_rejection_reason = Column(Text, nullable=True)
    
    # Completion
    is_completed = Column(Boolean, default=False)
    completed_at = Column(DateTime, nullable=True)
    
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


# ============================================================================
# ATTENDANCE SUMMARY CACHE
# ============================================================================

class AttendanceSummaryCache(Base):
    """Cached attendance summary for performance"""
    __tablename__ = "attendance_summary_cache"
    
    id = Column(Integer, primary_key=True, index=True)
    organization_id = Column(Integer, ForeignKey('organization.id'), nullable=False, index=True)
    employee_id = Column(Integer, ForeignKey('employees.id'), nullable=False, index=True)
    
    # Period
    summary_period = Column(String(20), nullable=False)  # 'weekly', 'monthly', 'yearly'
    period_start_date = Column(Date, nullable=False, index=True)
    period_end_date = Column(Date, nullable=False)
    
    # Attendance Summary
    total_working_days = Column(Integer, default=0)
    present_days = Column(Numeric(5, 2), default=0)
    absent_days = Column(Numeric(5, 2), default=0)
    half_days = Column(Numeric(5, 2), default=0)
    leave_days = Column(Numeric(5, 2), default=0)
    wfh_days = Column(Numeric(5, 2), default=0)
    on_duty_days = Column(Numeric(5, 2), default=0)
    weekend_days = Column(Integer, default=0)
    holiday_days = Column(Integer, default=0)
    
    # Hours
    total_work_hours = Column(Numeric(8, 2), default=0)
    required_work_hours = Column(Numeric(8, 2), default=0)
    overtime_hours = Column(Numeric(6, 2), default=0)
    
    # Punctuality
    late_arrivals = Column(Integer, default=0)
    early_departures = Column(Integer, default=0)
    
    # Leave Summary
    leave_taken = Column(Numeric(5, 2), default=0)
    leave_breakdown = Column(JSON, nullable=True)  # By leave type
    
    # Percentages
    attendance_percentage = Column(Numeric(5, 2), nullable=True)
    
    # Cache Metadata
    last_updated_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    is_stale = Column(Boolean, default=False)
    
    created_at = Column(DateTime, default=datetime.utcnow)
    
    __table_args__ = (
        Index('idx_summary_cache', 'employee_id', 'summary_period', 'period_start_date', unique=True),
    )


# ============================================================================
# CONFIGURATION & SETTINGS
# ============================================================================

class AttendanceConfiguration(Base):
    """Organization-level attendance configuration"""
    __tablename__ = "attendance_configuration"
    
    id = Column(Integer, primary_key=True, index=True)
    organization_id = Column(Integer, ForeignKey('organization.id'), nullable=False, unique=True, index=True)
    
    # Week Start Day
    week_start_day = Column(Integer, default=1)  # 0=Sunday, 1=Monday
    
    # Attendance Processing
    auto_process_attendance = Column(Boolean, default=True)
    processing_time = Column(Time, nullable=True)  # Daily processing time
    
    # Notifications
    send_missing_punch_notification = Column(Boolean, default=True)
    missing_punch_notification_time = Column(Time, nullable=True)
    send_late_arrival_notification = Column(Boolean, default=True)
    
    # Biometric Integration
    biometric_sync_enabled = Column(Boolean, default=True)
    biometric_sync_interval_minutes = Column(Integer, default=15)
    
    # Mobile App
    mobile_checkin_enabled = Column(Boolean, default=True)
    geofence_required_for_mobile = Column(Boolean, default=False)
    photo_capture_required = Column(Boolean, default=False)
    
    # Regularization
    auto_approve_regularization_threshold_minutes = Column(Integer, nullable=True)
    max_regularizations_per_month = Column(Integer, default=3)
    
    # Leave
    leave_approval_notification_enabled = Column(Boolean, default=True)
    leave_balance_low_threshold = Column(Numeric(4, 2), default=2.0)
    send_leave_balance_alerts = Column(Boolean, default=True)
    
    # Comp-off
    comp_off_expiry_days = Column(Integer, default=90)
    comp_off_expiry_alert_days = Column(Integer, default=7)
    
    # Reports
    default_report_timezone = Column(String(50), default='UTC')
    
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
class ShiftAssignment(Base):
    """Assign shifts to employees"""
    __tablename__ = "shift_assignments"
    
    id = Column(Integer, primary_key=True, index=True)
    uuid = Column(GUID(as_uuid=True), default=uuid.uuid4, unique=True, nullable=False)
    organization_id = Column(Integer, ForeignKey('organization.id'), nullable=False, index=True)
    
    employee_id = Column(Integer, ForeignKey('employees.id'), nullable=False, index=True)
    shift_id = Column(Integer, ForeignKey('shift_master.id'), nullable=False, index=True)
    
    # Assignment Period
    effective_from = Column(Date, nullable=False, index=True)
    effective_to = Column(Date, nullable=True, index=True)
    
    # For Rotating Shifts
    is_rotating = Column(Boolean, default=False)
    rotation_pattern = Column(JSON, nullable=True)  # Weekly rotation pattern
    
    is_active = Column(Boolean, default=True, index=True)
    
    # Audit Fields
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    created_by = Column(Integer, ForeignKey('employees.id'), nullable=True)
    
    # Soft Delete
    is_deleted = Column(Boolean, default=False, nullable=False)
    deleted_at = Column(DateTime, nullable=True)
    
    # Relationships
    employee = relationship("Employee", foreign_keys=[employee_id])
    shift = relationship("ShiftMaster", foreign_keys=[shift_id])
    
    __table_args__ = (
        Index('idx_shift_assign_emp_date', 'employee_id', 'effective_from', 'effective_to'),
    )


class ShiftRoster(Base):
    """Daily shift roster for employees"""
    __tablename__ = "shift_roster"
    
    id = Column(Integer, primary_key=True, index=True)
    uuid = Column(GUID(as_uuid=True), default=uuid.uuid4, unique=True, nullable=False)
    organization_id = Column(Integer, ForeignKey('organization.id'), nullable=False, index=True)
    
    employee_id = Column(Integer, ForeignKey('employees.id'), nullable=False, index=True)
    shift_id = Column(Integer, ForeignKey('shift_master.id'), nullable=False)
    roster_date = Column(Date, nullable=False, index=True)
    
    # Override Times (if different from shift master)
    actual_start_time = Column(Time, nullable=True)
    actual_end_time = Column(Time, nullable=True)
    
    # Week-off
    is_week_off = Column(Boolean, default=False)
    is_working_on_week_off = Column(Boolean, default=False)
    
    # Status
    is_published = Column(Boolean, default=False)
    
    # Notes
    notes = Column(Text, nullable=True)
    
    # Audit Fields
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    created_by = Column(Integer, ForeignKey('employees.id'), nullable=True)

    # Soft Delete
    is_deleted = Column(Boolean, default=False, nullable=False)
    deleted_at = Column(DateTime, nullable=True)

    # Relationships
    employee = relationship("Employee", foreign_keys=[employee_id])
    shift = relationship("ShiftMaster", foreign_keys=[shift_id])
    
    __table_args__ = (
        Index('idx_roster_emp_date', 'employee_id', 'roster_date', unique=True),
        Index('idx_roster_org_date', 'organization_id', 'roster_date'),
    )


# ============================================================================
# ATTENDANCE - ATTENDANCE RECORDS
# ============================================================================

class AttendanceRecord(Base):
    """Daily attendance records"""
    __tablename__ = "attendance_records"
    
    id = Column(Integer, primary_key=True, index=True)
    uuid = Column(GUID(as_uuid=True), default=uuid.uuid4, unique=True, nullable=False, index=True)
    organization_id = Column(Integer, ForeignKey('organization.id'), nullable=False, index=True)
    
    employee_id = Column(Integer, ForeignKey('employees.id'), nullable=False, index=True)
    attendance_date = Column(Date, nullable=False, index=True)
    
    # Shift Information
    shift_id = Column(Integer, ForeignKey('shift_master.id'), nullable=True)
    shift_start_time = Column(Time, nullable=True)
    shift_end_time = Column(Time, nullable=True)
    
    # Check In/Out Times
    first_check_in = Column(DateTime, nullable=True)
    last_check_out = Column(DateTime, nullable=True)
    
    # Working Hours
    total_work_hours = Column(Numeric(5, 2), default=0)
    break_hours = Column(Numeric(4, 2), default=0)
    net_work_hours = Column(Numeric(5, 2), default=0)
    
    # Overtime
    overtime_hours = Column(Numeric(5, 2), default=0)
    overtime_approved = Column(Boolean, default=False)
    
    # Status
    status = Column(Enum(AttendanceStatus), nullable=False, index=True)
    
    # Late/Early
    is_late = Column(Boolean, default=False, index=True)
    late_by_minutes = Column(Integer, default=0)
    is_early_departure = Column(Boolean, default=False)
    early_departure_minutes = Column(Integer, default=0)
    is_late_departure = Column(Boolean, default=False)
    late_departure_minutes = Column(Integer, default=0)
    
    # Location Information
    check_in_location = Column(String(255), nullable=True)
    check_in_latitude = Column(Numeric(10, 8), nullable=True)
    check_in_longitude = Column(Numeric(11, 8), nullable=True)
    check_out_location = Column(String(255), nullable=True)
    check_out_latitude = Column(Numeric(10, 8), nullable=True)
    check_out_longitude = Column(Numeric(11, 8), nullable=True)
    
    # Source
    check_in_source = Column(Enum(AttendanceSource), nullable=True)
    check_out_source = Column(Enum(AttendanceSource), nullable=True)
    
    # Device Information
    check_in_device_id = Column(String(100), nullable=True)
    check_out_device_id = Column(String(100), nullable=True)
    check_in_ip_address = Column(String(50), nullable=True)
    check_out_ip_address = Column(String(50), nullable=True)
    
    # Regularization
    is_regularized = Column(Boolean, default=False, index=True)
    regularization_id = Column(Integer, ForeignKey('attendance_regularizations.id'), nullable=True)
    
    # Manual Entry
    is_manual_entry = Column(Boolean, default=False)
    manual_entry_reason = Column(Text, nullable=True)
    
    # Leave/Holiday
    leave_id = Column(Integer, ForeignKey('leave_applications.id'), nullable=True)
    is_holiday = Column(Boolean, default=False)
    holiday_id = Column(Integer, ForeignKey('holidays.id'), nullable=True)
    
    # Remarks
    remarks = Column(Text, nullable=True)
    
    # Audit Fields
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    created_by = Column(Integer, ForeignKey('employees.id'), nullable=True)
    
    # Relationships
    employee = relationship("Employee", foreign_keys=[employee_id])
    shift = relationship("ShiftMaster", foreign_keys=[shift_id])

    __table_args__ = (
        Index('idx_attendance_emp_date', 'employee_id', 'attendance_date', unique=True),
        Index('idx_attendance_org_date', 'organization_id', 'attendance_date'),
        Index('idx_attendance_status', 'organization_id', 'attendance_date', 'status'),
        Index('idx_attendance_emp_status_date', 'employee_id', 'status', 'attendance_date'),
    )


class AttendanceLog(Base):
    """Raw attendance punches/logs"""
    __tablename__ = "attendance_logs"
    
    id = Column(Integer, primary_key=True, index=True)
    uuid = Column(GUID(as_uuid=True), default=uuid.uuid4, unique=True, nullable=False)
    organization_id = Column(Integer, ForeignKey('organization.id'), nullable=False, index=True)
    
    employee_id = Column(Integer, ForeignKey('employees.id'), nullable=False, index=True)
    punch_time = Column(DateTime, nullable=False, index=True)
    punch_date = Column(Date, nullable=False, index=True)
    
    # Check Type
    check_type = Column(Enum(CheckType), nullable=False)
    
    # Source & Device
    source = Column(Enum(AttendanceSource), nullable=False)
    device_id = Column(String(100), nullable=True, index=True)
    device_name = Column(String(150), nullable=True)
    
    # Location
    location = Column(String(255), nullable=True)
    latitude = Column(Numeric(10, 8), nullable=True)
    longitude = Column(Numeric(11, 8), nullable=True)
    
    # Geofencing Validation
    is_within_geofence = Column(Boolean, nullable=True)
    geofence_name = Column(String(150), nullable=True)
    
    # Network Info
    ip_address = Column(String(50), nullable=True)
    mac_address = Column(String(50), nullable=True)
    
    # Biometric Info
    biometric_template_id = Column(String(100), nullable=True)
    biometric_score = Column(Integer, nullable=True)
    
    # Photo Capture
    photo_url = Column(String(500), nullable=True)
    
    # Processing Status
    is_processed = Column(Boolean, default=False, index=True)
    processed_at = Column(DateTime, nullable=True)
    attendance_record_id = Column(Integer, ForeignKey('attendance_records.id'), nullable=True)
    
    # Validation
    is_valid = Column(Boolean, default=True)
    validation_notes = Column(Text, nullable=True)
    
    # Audit Fields
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    employee = relationship("Employee", foreign_keys=[employee_id])

    __table_args__ = (
        Index('idx_log_emp_date', 'employee_id', 'punch_date'),
        Index('idx_log_device', 'device_id', 'punch_time'),
        Index('idx_log_processed', 'is_processed', 'punch_date'),
        Index('idx_attendance_log_emp_punch', 'employee_id', 'punch_date', 'punch_time'),
    )


class AttendanceRegularization(Base):
    """Attendance regularization requests"""
    __tablename__ = "attendance_regularizations"
    
    id = Column(Integer, primary_key=True, index=True)
    uuid = Column(GUID(as_uuid=True), default=uuid.uuid4, unique=True, nullable=False, index=True)
    organization_id = Column(Integer, ForeignKey('organization.id'), nullable=False, index=True)
    
    employee_id = Column(Integer, ForeignKey('employees.id'), nullable=False, index=True)
    attendance_date = Column(Date, nullable=False, index=True)
    
    # Original Values
    original_check_in = Column(DateTime, nullable=True)
    original_check_out = Column(DateTime, nullable=True)
    
    # Requested Values
    requested_check_in = Column(DateTime, nullable=True)
    requested_check_out = Column(DateTime, nullable=True)
    
    # Reason
    reason = Column(Text, nullable=False)
    reason_category = Column(String(50), nullable=True)  # 'forgot_punch', 'system_error', 'client_visit'
    
    # Supporting Documents
    attachment_urls = Column(JSON, nullable=True)
    
    # Approval Workflow
    status = Column(Enum(RegularizationStatus), default=RegularizationStatus.PENDING, nullable=False, index=True)
    approver_id = Column(Integer, ForeignKey('employees.id'), nullable=True, index=True)
    approved_at = Column(DateTime, nullable=True)
    approver_comments = Column(Text, nullable=True)
    
    # Rejection
    rejection_reason = Column(Text, nullable=True)
    
    # Audit Fields
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    is_deleted = Column(Boolean, default=False, nullable=False, index=True)
    
    # Relationships
    employee = relationship("Employee", foreign_keys=[employee_id])
    approver = relationship("Employee", foreign_keys=[approver_id])
    
    __table_args__ = (
        Index('idx_regular_emp_date', 'employee_id', 'attendance_date'),
        Index('idx_regular_status', 'status', 'approver_id'),
    )


# ============================================================================
# ATTENDANCE - OVERTIME MANAGEMENT
# ============================================================================

class OvertimeRequest(Base):
    """Overtime requests and approvals"""
    __tablename__ = "overtime_requests"
    
    id = Column(Integer, primary_key=True, index=True)
    uuid = Column(GUID(as_uuid=True), default=uuid.uuid4, unique=True, nullable=False, index=True)
    organization_id = Column(Integer, ForeignKey('organization.id'), nullable=False, index=True)
    
    employee_id = Column(Integer, ForeignKey('employees.id'), nullable=False, index=True)
    attendance_date = Column(Date, nullable=False, index=True)
    attendance_record_id = Column(Integer, ForeignKey('attendance_records.id'), nullable=True)
    
    # Overtime Details
    overtime_hours = Column(Numeric(5, 2), nullable=False)
    overtime_start_time = Column(DateTime, nullable=True)
    overtime_end_time = Column(DateTime, nullable=True)
    
    # Pre-approved or Post-facto
    is_pre_approved = Column(Boolean, default=False)
    
    # Reason & Work Details
    reason = Column(Text, nullable=False)
    work_description = Column(Text, nullable=True)
    project_id = Column(Integer, nullable=True)
    task_id = Column(Integer, nullable=True)
    
    # Compensation Type
    compensation_type = Column(Enum(CompensationType), nullable=True, default=CompensationType.paid)  # 'paid', 'comp_off', 'both'
    comp_off_applicable = Column(Numeric(5, 2), nullable=True)  # Days
    
    # Approval Workflow
    status = Column(Enum(OvertimeStatus), default=OvertimeStatus.PENDING, nullable=False, index=True)
    approver_id = Column(Integer, ForeignKey('employees.id'), nullable=True, index=True)
    approved_at = Column(DateTime, nullable=True)
    approver_comments = Column(Text, nullable=True)
    rejection_reason = Column(Text, nullable=True)
    
    # Payment Processing
    is_paid = Column(Boolean, default=False)
    paid_amount = Column(Numeric(10, 2), nullable=True)
    payment_date = Column(Date, nullable=True)
    payroll_period_id = Column(Integer, nullable=True)
    
    # Comp-off Generation
    comp_off_generated = Column(Boolean, default=False)
    comp_off_id = Column(Integer, ForeignKey('compensatory_offs.id'), nullable=True)
    
    # Audit Fields
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    employee = relationship("Employee", foreign_keys=[employee_id])
    approver = relationship("Employee", foreign_keys=[approver_id])
    attendance_record = relationship("AttendanceRecord", foreign_keys=[attendance_record_id])

    __table_args__ = (
        Index('idx_overtime_emp_date', 'employee_id', 'attendance_date'),
        Index('idx_overtime_status', 'status', 'approver_id'),
        Index('idx_overtime_emp_status_date', 'employee_id', 'status', 'attendance_date'),
    )


# ============================================================================
# ATTENDANCE - TIMESHEET MANAGEMENT
# ============================================================================

class Timesheet(Base):
    """Weekly/Monthly timesheets"""
    __tablename__ = "timesheets"
    
    id = Column(Integer, primary_key=True, index=True)
    uuid = Column(GUID(as_uuid=True), default=uuid.uuid4, unique=True, nullable=False, index=True)
    organization_id = Column(Integer, ForeignKey('organization.id'), nullable=False, index=True)
    
    employee_id = Column(Integer, ForeignKey('employees.id'), nullable=False, index=True)
    
    # Period
    period_start_date = Column(Date, nullable=False, index=True)
    period_end_date = Column(Date, nullable=False, index=True)
    period_type = Column(String(20), nullable=False)  # 'weekly', 'bi_weekly', 'monthly'
    
    # Hours Summary
    total_hours = Column(Numeric(6, 2), default=0)
    billable_hours = Column(Numeric(6, 2), default=0)
    non_billable_hours = Column(Numeric(6, 2), default=0)
    
    # Status
    status = Column(Enum(TimesheetStatus), default=TimesheetStatus.DRAFT, nullable=False, index=True)
    
    # Submission
    submitted_at = Column(DateTime, nullable=True)
    submitted_by = Column(Integer, ForeignKey('employees.id'), nullable=True)
    
    # Approval
    approver_id = Column(Integer, ForeignKey('employees.id'), nullable=True, index=True)
    approved_at = Column(DateTime, nullable=True)
    approver_comments = Column(Text, nullable=True)
    
    # Rejection
    rejection_reason = Column(Text, nullable=True)
    rejected_at = Column(DateTime, nullable=True)
    
    # Notes
    notes = Column(Text, nullable=True)
    
    # Audit Fields
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    is_deleted = Column(Boolean, default=False)
    
    __table_args__ = (
        Index('idx_timesheet_emp_period', 'employee_id', 'period_start_date', 'period_end_date'),
        Index('idx_timesheet_status', 'status', 'approver_id'),
        Index('idx_timesheet_emp_period_status', 'employee_id', 'period_start_date', 'status'),
    )

    # Relationships
    employee = relationship("Employee", foreign_keys=[employee_id])
    approver = relationship("Employee", foreign_keys=[approver_id])
    entries = relationship("TimesheetEntry", back_populates="timesheet")


class TimesheetEntry(Base):
    """Daily timesheet entries with project/task allocation"""
    __tablename__ = "timesheet_entries"
    
    id = Column(Integer, primary_key=True, index=True)
    uuid = Column(GUID(as_uuid=True), default=uuid.uuid4, unique=True, nullable=False)
    
    timesheet_id = Column(Integer, ForeignKey('timesheets.id'), nullable=False, index=True)
    employee_id = Column(Integer, ForeignKey('employees.id'), nullable=False, index=True)
    entry_date = Column(Date, nullable=False, index=True)
    
    # Project/Task Allocation — FK-linked to master tables
    # Legacy free-text fields are preserved as cache/fallback for old entries
    project_id = Column(Integer, ForeignKey('projects.id'), nullable=True, index=True)
    project_name = Column(String(200), nullable=True)  # Cache / fallback for legacy entries
    task_id = Column(Integer, ForeignKey('project_tasks.id'), nullable=True)   # Required by policy
    task_name = Column(String(200), nullable=True)     # Cache / fallback
    activity_type_id = Column(Integer, ForeignKey('activity_types.id'), nullable=True)
    activity_description = Column(Text, nullable=True)
    
    # Hours
    hours_worked = Column(Numeric(5, 2), nullable=False)
    is_billable = Column(Boolean, default=True)

    # Client resolved via project → client (kept as cache for legacy)
    client_id = Column(Integer, nullable=True)          # Legacy field — no FK
    client_name = Column(String(200), nullable=True)    # Cache / fallback
    
    # Notes
    notes = Column(Text, nullable=True)
    
    # Audit Fields
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    is_deleted = Column(Boolean, default=False)

    # Relationships
    timesheet = relationship("Timesheet", back_populates="entries")
    project = relationship("Project", foreign_keys=[project_id], lazy="joined")
    task = relationship("ProjectTask", foreign_keys=[task_id], lazy="joined")

    @property
    def project_uuid(self):
        return self.project.uuid if self.project else None

    @property
    def task_uuid(self):
        return self.task.uuid if self.task else None

    @property
    def client(self):
        # Resolve via project -> client if available
        if self.project:
            return self.project.client
        return None

    @property
    def client_uuid(self):
        # Resolve via project -> client if available
        if self.project and self.project.client:
            return self.project.client.uuid
        return None


# ============================================================================
# LEAVE - LEAVE TYPES & POLICIES
# ============================================================================

class LeaveType(Base):
    """Leave type master"""
    __tablename__ = "leave_types"
    
    id = Column(Integer, primary_key=True, index=True)
    uuid = Column(GUID(as_uuid=True), default=uuid.uuid4, unique=True, nullable=False, index=True)
    organization_id = Column(Integer, ForeignKey('organization.id'), nullable=False, index=True)
    
    leave_code = Column(String(50), nullable=False, index=True)
    leave_name = Column(String(150), nullable=False)
    description = Column(Text, nullable=True)
    
    # Leave Configuration
    is_paid = Column(Boolean, default=True)
    is_encashable = Column(Boolean, default=False)
    is_carry_forward = Column(Boolean, default=False)
    max_carry_forward = Column(Numeric(5, 2), nullable=True)
    
    # Accrual Settings
    accrual_type = Column(Enum(LeaveAccrualType), nullable=False)
    accrual_rate = Column(Numeric(5, 2), nullable=False)  # Leaves per period
    accrual_start_month = Column(Integer, nullable=True)  # For yearly/financial year
    
    # Balance Settings
    max_balance = Column(Numeric(6, 2), nullable=True)
    min_balance_for_application = Column(Numeric(5, 2), default=0)
    allow_negative_balance = Column(Boolean, default=False)
    max_negative_balance = Column(Numeric(5, 2), default=0)
    
    # Application Rules
    min_leaves_per_application = Column(Numeric(4, 2), default=0.5)
    max_leaves_per_application = Column(Numeric(5, 2), nullable=True)
    min_advance_days = Column(Integer, default=0)  # Days before leave start
    max_backdated_days = Column(Integer, default=0)
    
    # Unit Type
    unit_type = Column(Enum(LeaveUnitType), default=LeaveUnitType.FULL_DAY, nullable=False)
    
    # Consecutive Leave Limits
    max_consecutive_days = Column(Integer, nullable=True)
    
    # Weekend/Holiday Inclusion
    include_weekends = Column(Boolean, default=False)
    include_holidays = Column(Boolean, default=False)
    
    # Documentation Required
    documentation_required = Column(Boolean, default=False)
    documentation_required_after_days = Column(Integer, nullable=True)
    
    # Approval Workflow
    requires_approval = Column(Boolean, default=True)
    approval_levels = Column(Integer, default=1)
    
    # Gender Specific
    gender_specific = Column(String(20), nullable=True)  # 'male', 'female', null=all
    
    # Probation Applicable
    applicable_during_probation = Column(Boolean, default=False)
    available_after_months = Column(Integer, default=0)
    
    # Display Settings
    color_code = Column(String(20), nullable=True)
    display_order = Column(Integer, default=0)
    
    is_active = Column(Boolean, default=True, index=True)
    
    # Audit Fields
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    created_by = Column(Integer, ForeignKey('employees.id'), nullable=True)
    is_deleted = Column(Boolean, default=False, index=True)
    deleted_at = Column(DateTime, nullable=True)
    
    __table_args__ = (
        Index('idx_leave_type_org_code', 'organization_id', 'leave_code', unique=True),
    )


class LeavePolicy(Base):
    """Leave policies for different employee groups"""
    __tablename__ = "leave_policies"
    
    id = Column(Integer, primary_key=True, index=True)
    uuid = Column(GUID(as_uuid=True), default=uuid.uuid4, unique=True, nullable=False)
    organization_id = Column(Integer, ForeignKey('organization.id'), nullable=False, index=True)
    
    policy_name = Column(String(150), nullable=False)
    description = Column(Text, nullable=True)
    
    # Applicability
    applicable_to = Column(String(50), nullable=True)  # 'all', 'department', 'location', 'grade'
    department_ids = Column(JSON, nullable=True)
    location_ids = Column(JSON, nullable=True)
    employment_types = Column(JSON, nullable=True)
    
    # Effective Date
    effective_from = Column(Date, nullable=False)
    effective_to = Column(Date, nullable=True)
    
    is_active = Column(Boolean, default=True)
    is_default = Column(Boolean, default=False)
    
    # Audit Fields
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    created_by = Column(Integer, ForeignKey('employees.id'), nullable=True)
    is_deleted = Column(Boolean, default=False, index=True)
    deleted_at = Column(DateTime, nullable=True)
    
    # Relationships
    mappings = relationship("LeavePolicyMapping", back_populates="policy")


class LeavePolicyMapping(Base):
    """Map leave types to policies with specific rules"""
    __tablename__ = "leave_policy_mappings"
    
    id = Column(Integer, primary_key=True, index=True)
    leave_policy_id = Column(Integer, ForeignKey('leave_policies.id'), nullable=False, index=True)
    leave_type_id = Column(Integer, ForeignKey('leave_types.id'), nullable=False, index=True)
    
    # Override Settings (if different from leave type master)
    annual_quota = Column(Numeric(5, 2), nullable=True)
    accrual_rate_override = Column(Numeric(5, 2), nullable=True)
    
    is_active = Column(Boolean, default=True)
    
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    created_by = Column(Integer, ForeignKey('employees.id'), nullable=True)
    
    # Relationships
    policy = relationship("LeavePolicy", back_populates="mappings")
    leave_type = relationship("LeaveType")
    
    __table_args__ = (
        Index('idx_policy_mapping', 'leave_policy_id', 'leave_type_id', unique=True),
    )