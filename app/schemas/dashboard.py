from typing import List, Optional, Any
from pydantic import BaseModel, UUID4
from datetime import datetime, date, time
from app.schemas.analytics import AttendanceKPIs, LeaveKPIs, AttendanceMetricData
from app.schemas.attendance import AttendanceStatus, CheckType, ShiftSchema
from app.schemas.leave import LeaveBalanceSchema

# ============================================================================
# MINIMAL SCHEMAS FOR DISPLAY
# ============================================================================

class MinimalLeaveBalance(BaseModel):
    leave_type_name: str
    available_balance: float
    total_balance: float

class MinimalShift(BaseModel):
    shift_name: str
    start_time: time
    end_time: time
    shift_type: str

class MinimalPunch(BaseModel):
    punch_time: datetime
    check_type: CheckType
    location: Optional[str] = None

class ManagerChainItem(BaseModel):
    name: str
    job_title: Optional[str] = None
    photograph_url: Optional[str] = None
    level: int # 1 = Immediate Manager, 2 = Next level, etc.

class UpcomingLeave(BaseModel):
    leave_type_name: str
    from_date: date
    to_date: date
    status: str
    total_days: float

class RecentRequest(BaseModel):
    request_type: str # 'Overtime', 'Regularization', 'Encashment', 'CompOff'
    request_date: date
    status: str
    details: str
    created_at: datetime

class ExpiringItem(BaseModel):
    item_name: str
    item_type: str # 'Document' or 'Certification'
    expiry_date: date
    days_remaining: int

class DailyRoster(BaseModel):
    roster_date: date
    shift_name: Optional[str] = None
    start_time: Optional[time] = None
    end_time: Optional[time] = None
    is_week_off: bool = False

# ============================================================================
# EMPLOYEE DASHBOARD SCHEMAS
# ============================================================================

class EmployeeAttendanceStatus(BaseModel):
    is_checked_in: bool
    is_on_break: bool
    last_punch_type: Optional[CheckType] = None
    last_punch_time: Optional[datetime] = None
    total_work_hours: float = 0.0
    net_work_hours: float = 0.0
    total_break_hours: float = 0.0
    # New Fields
    is_late: bool = False
    late_minutes: int = 0
    is_early_departure: bool = False
    early_departure_minutes: int = 0
    is_late_departure: bool = False
    late_departure_minutes: int = 0

class UpcomingHoliday(BaseModel):
    holiday_name: str
    holiday_date: date
    day_name: str

class EmployeeDashboardData(BaseModel):
    attendance: EmployeeAttendanceStatus
    leave_balances: List[MinimalLeaveBalance]
    current_shift: Optional[MinimalShift] = None
    upcoming_holidays: List[UpcomingHoliday]
    recent_punches: List[MinimalPunch]
    # New Fields
    upcoming_leaves: List[UpcomingLeave]
    weekly_roster: List[DailyRoster]
    manager_chain: List[ManagerChainItem]
    recent_requests: List[RecentRequest]
    expiring_items: List[ExpiringItem]

class EmployeeDashboardResponse(BaseModel):
    success: bool
    message: str
    data: EmployeeDashboardData

# ============================================================================
# ORGANIZATION DASHBOARD SCHEMAS
# ============================================================================

class OrganizationSnapshot(BaseModel):
    total_employees: int
    present_today: int
    absent_today: int
    on_leave_today: int
    late_today: int

class ApprovalCounts(BaseModel):
    pending_leaves: int
    pending_regularizations: int
    pending_overtime: int
    pending_wfh: int
    pending_on_duty: int

class OrganizationDashboardData(BaseModel):
    snapshot: OrganizationSnapshot
    approvals: ApprovalCounts
    attendance_kpis: AttendanceKPIs
    leave_kpis: LeaveKPIs
    department_wise_attendance: List[AttendanceMetricData]

class OrganizationDashboardResponse(BaseModel):
    success: bool
    message: str
    data: OrganizationDashboardData
