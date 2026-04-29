from typing import List, Optional, Dict, Any, Union
from pydantic import BaseModel
from datetime import date, datetime
from pydantic import UUID4
from enum import Enum
from app.schemas.employee import EmployeeMinimalSchema

class DemographicsGroupBy(str, Enum):
    AGE = "age"
    GENDER = "gender"
    DEPARTMENT = "department"
    LOCATION = "location"
    EMPLOYMENT_TYPE = "employment_type"
    EMPLOYMENT_STATUS = "employment_status"

class EmployeeDemographicsRequest(BaseModel):
    department_uuid: Optional[UUID4] = None
    location_uuid: Optional[UUID4] = None
    group_by: DemographicsGroupBy

class DemographicGroupData(BaseModel):
    group: str
    count: int
    percentage: float

class EmployeeDemographicsResponse(BaseModel):
    success: bool
    message: str
    total_employees: int
    group_by: str
    data: List[DemographicGroupData]

class HeadcountTrendData(BaseModel):
    date: date
    total_headcount: int
    new_joiners: int
    leavers: int
    net_change: int

class HeadcountReportResponse(BaseModel):
    success: bool
    message: str
    from_date: date
    to_date: date
    current_headcount: int
    total_new_joiners: int
    total_leavers: int
    trends: List[HeadcountTrendData]

class NewHireReportResponse(BaseModel):
    success: bool
    message: str
    from_date: date
    to_date: date
    total_new_hires: int
    data: List[EmployeeMinimalSchema]

class EmployeeExitReportResponse(BaseModel):
    success: bool
    message: str
    from_date: date
    to_date: date
    total_exits: int
    data: List[EmployeeMinimalSchema]

class ProbationStatus(str, Enum):
    UPCOMING = "upcoming"
    OVERDUE = "overdue"
    COMPLETED = "completed"

class EmployeeProbationSchema(EmployeeMinimalSchema):
    probation_end_date: Optional[date]
    days_remaining: Optional[int] = None
    probation_status: Optional[str] = None # Calculated field

class ProbationReportResponse(BaseModel):
    success: bool
    message: str
    status_filter: Optional[str]
    total_records: int
    data: List[EmployeeProbationSchema]

class EmployeeAnniversarySchema(EmployeeMinimalSchema):
    original_joining_date: date
    years_completed: int
    anniversary_date: date

class AnniversaryReportResponse(BaseModel):
    success: bool
    message: str
    month_filter: Optional[int]
    total_records: int
    data: List[EmployeeAnniversarySchema]

class EmployeeBirthdaySchema(EmployeeMinimalSchema):
    date_of_birth: date
    current_birthday: date
    age: int

class BirthdayReportResponse(BaseModel):
    success: bool
    message: str
    month_filter: Optional[int]
    total_records: int
    data: List[EmployeeBirthdaySchema]

class AttendanceStats(BaseModel):
    present: int = 0
    absent: int = 0
    leave: int = 0
    half_day: int = 0
    late_arrival: int = 0
    early_departure: int = 0
    avg_work_hours: float = 0.0

class AttendanceTrend(BaseModel):
    date: date
    present_percentage: float
    absent_percentage: float

class AttendanceSummaryReportResponse(BaseModel):
    success: bool
    message: str
    from_date: date
    to_date: date
    total_working_days: int
    stats: AttendanceStats
    trends: List[AttendanceTrend]

class DailyAttendanceRecord(BaseModel):
    employee_uuid: UUID4
    employee_name: str
    employee_code: str
    department: Optional[str] = None
    location: Optional[str] = None
    status: str
    check_in: Optional[datetime] = None
    check_out: Optional[datetime] = None
    work_hours: float = 0.0
    is_late: bool = False
    is_early_departure: bool = False

class DailyAttendanceReportResponse(BaseModel):
    success: bool
    message: str
    date: date
    total_records: int
    data: List[DailyAttendanceRecord]

class MonthlyAttendanceSummary(BaseModel):
    present: int = 0
    absent: int = 0
    half_day: int = 0
    on_leave: int = 0
    late_arrivals: int = 0
    early_departures: int = 0
    total_work_hours: float = 0.0
    avg_work_hours: float = 0.0

class MonthlyAttendanceRecord(BaseModel):
    employee_uuid: UUID4
    employee_name: str
    employee_code: str
    department: Optional[str] = None
    summary: MonthlyAttendanceSummary

class MonthlyAttendanceReportResponse(BaseModel):
    success: bool
    message: str
    month: int
    year: int
    total_records: int
    data: List[MonthlyAttendanceRecord]

class LateArrivalRecord(BaseModel):
    employee_uuid: UUID4
    employee_name: str
    employee_code: str
    department: Optional[str] = None
    date: date
    shift_start_time: Optional[datetime] = None
    actual_check_in: Optional[datetime] = None
    late_minutes: int

class LateArrivalReportResponse(BaseModel):
    success: bool
    message: str
    from_date: date
    to_date: date
    total_instances: int
    data: List[LateArrivalRecord]

class EarlyDepartureRecord(BaseModel):
    employee_uuid: UUID4
    employee_name: str
    employee_code: str
    department: Optional[str] = None
    date: date
    shift_end_time: Optional[datetime] = None
    actual_check_out: Optional[datetime] = None
    early_departure_minutes: int

class EarlyDepartureReportResponse(BaseModel):
    success: bool
    message: str
    from_date: date
    to_date: date
    total_instances: int
    data: List[EarlyDepartureRecord]

class AbsenteeismTrend(BaseModel):
    date: date
    absent_count: int
    absenteeism_rate: float

class AbsenteeismReportResponse(BaseModel):
    success: bool
    message: str
    from_date: date
    to_date: date
    total_active_employees: int
    overall_absenteeism_rate: float
    trends: List[AbsenteeismTrend]

class OvertimeReportRecord(BaseModel):
    employee_uuid: UUID4
    employee_name: str
    employee_code: str
    department: Optional[str] = None
    date: date
    requested_hours: float
    approved_hours: float
    cost: float = 0.0
    status: str
    is_paid: bool

class OvertimeReportResponse(BaseModel):
    success: bool
    message: str
    from_date: date
    to_date: date
    total_requested_hours: float
    total_approved_hours: float
    total_cost: float
    data: List[OvertimeReportRecord]

class LeaveUtilizationData(BaseModel):
    leave_type_name: str
    leave_type_code: str
    total_applied_days: float
    total_approved_days: float
    total_rejected_days: float
    utilization_percentage: float # (Approved / Applied) * 100 or relative to quota if available

class LeaveSummaryReportResponse(BaseModel):
    success: bool
    message: str
    from_date: date
    to_date: date
    total_applications: int
    total_approved_days: float
    utilization: List[LeaveUtilizationData]

class LeaveBalanceRecord(BaseModel):
    employee_uuid: UUID4
    employee_name: str
    employee_code: str
    department: Optional[str] = None
    leave_type_name: str
    leave_type_code: str
    opening_balance: float
    accrued: float
    used: float
    available_balance: float

class LeaveBalanceReportResponse(BaseModel):
    success: bool
    message: str
    year: int
    total_records: int
    data: List[LeaveBalanceRecord]

class LeaveTrendData(BaseModel):
    date: date
    leave_count: int
    approved_days: float

class LeaveTrendsReportResponse(BaseModel):
    success: bool
    message: str
    from_date: date
    to_date: date
    trends: List[LeaveTrendData]

class PendingLeaveRecord(BaseModel):
    application_uuid: UUID4
    employee_uuid: UUID4
    employee_name: str
    employee_code: str
    department: Optional[str] = None
    leave_type: str
    from_date: date
    to_date: date
    total_days: float
    current_approver_name: Optional[str] = None
    applied_date: date

class PendingLeaveReportResponse(BaseModel):
    success: bool
    message: str
    total_pending: int
    data: List[PendingLeaveRecord]

class LeaveEncashmentRecord(BaseModel):
    employee_uuid: UUID4
    employee_name: str
    employee_code: str
    department: Optional[str] = None
    leave_type: str
    encashment_date: date
    encashment_days: float
    encashment_amount: float
    tax_deducted: float
    net_amount: float
    status: str
    is_paid: bool

class LeaveEncashmentReportResponse(BaseModel):
    success: bool
    message: str
    from_date: date
    to_date: date
    total_encashed_days: float
    total_encashed_amount: float
    data: List[LeaveEncashmentRecord]

class CompOffRecord(BaseModel):
    employee_uuid: UUID4
    employee_name: str
    employee_code: str
    department: Optional[str] = None
    worked_date: date
    comp_off_days: float
    source_type: str
    expiry_date: date
    is_utilized: bool
    utilized_days: float
    remaining_days: float
    utilized_date: Optional[date] = None

class CompOffReportResponse(BaseModel):
    success: bool
    message: str
    from_date: date
    to_date: date
    total_credited_days: float
    total_utilized_days: float
    data: List[CompOffRecord]
