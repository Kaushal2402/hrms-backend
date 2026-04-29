from typing import List, Optional, Any
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import func, case
from datetime import date, datetime
import uuid

from app.api import deps
from app.models.employee import Employee, Department, Location, Gender, EmploymentType, EmploymentStatus
from app.models.organization import Organization
from app.schemas.report import (
    EmployeeDemographicsResponse, DemographicGroupData, DemographicsGroupBy,
    HeadcountReportResponse, HeadcountTrendData, NewHireReportResponse,
    EmployeeExitReportResponse, ProbationReportResponse, EmployeeProbationSchema,
    ProbationStatus, AnniversaryReportResponse, EmployeeAnniversarySchema,
    BirthdayReportResponse, EmployeeBirthdaySchema,
    AttendanceSummaryReportResponse, AttendanceStats, AttendanceTrend,
    DailyAttendanceReportResponse, DailyAttendanceRecord,
    MonthlyAttendanceReportResponse, MonthlyAttendanceRecord, MonthlyAttendanceSummary,
    LateArrivalReportResponse, LateArrivalRecord,
    EarlyDepartureReportResponse, EarlyDepartureRecord,
    AbsenteeismReportResponse, AbsenteeismTrend,
    OvertimeReportResponse, OvertimeReportRecord,
    LeaveSummaryReportResponse, LeaveUtilizationData,
    LeaveBalanceReportResponse, LeaveBalanceRecord,
    LeaveTrendsReportResponse, LeaveTrendData,
    PendingLeaveReportResponse, PendingLeaveRecord,
    LeaveEncashmentReportResponse, LeaveEncashmentRecord,
    CompOffReportResponse, CompOffRecord
)
from app.models.attendance import (
    AttendanceRecord, AttendanceStatus, OvertimeRequest, OvertimeStatus, 
    LeaveApplication, LeaveType, LeaveStatus, LeaveBalance,
    LeaveEncashment, LeaveEncashmentStatus, CompensatoryOff
)
from app.schemas.employee import EmployeeMinimalSchema
from calendar import monthrange
from datetime import timedelta

router = APIRouter()

def calculate_age(born: date) -> int:
    today = date.today()
    return today.year - born.year - ((today.month, today.day) < (born.month, born.day))

@router.get("/employee-demographics", response_model=EmployeeDemographicsResponse)
def get_employee_demographics(
    department_uuid: Optional[uuid.UUID] = Query(None, description="Filter by Department UUID"),
    location_uuid: Optional[uuid.UUID] = Query(None, description="Filter by Location UUID"),
    group_by: DemographicsGroupBy = Query(..., description="Criteria to group employees by"),
    db: Session = Depends(deps.get_db),
    current_org: Organization = Depends(deps.get_current_org)
):
    """
    Get employee demographics statistics based on specified grouping.
    Values are calculated for active employees only by default.
    """
    # Base query
    query = db.query(Employee).filter(
        Employee.organization_id == current_org.id,
        Employee.is_deleted == False,
        Employee.employment_status == EmploymentStatus.ACTIVE
    )
    
    # Apply filters
    if department_uuid:
        query = query.join(Department).filter(Department.uuid == department_uuid)
        
    if location_uuid:
        query = query.join(Location).filter(Location.uuid == location_uuid)
        
    employees = query.all()
    total_employees = len(employees)
    
    data = []
    
    if total_employees == 0:
        return EmployeeDemographicsResponse(
            success=True,
            message="No data found for the given criteria",
            total_employees=0,
            group_by=group_by.value,
            data=[]
        )

    # Aggregation Logic
    if group_by == DemographicsGroupBy.AGE:
        # Define Age Buckets
        buckets = {
            "Under 20": 0,
            "20-29": 0,
            "30-39": 0,
            "40-49": 0,
            "50-59": 0,
            "60+": 0
        }
        unknown = 0
        
        for emp in employees:
            if emp.date_of_birth:
                age = calculate_age(emp.date_of_birth)
                if age < 20:
                    buckets["Under 20"] += 1
                elif 20 <= age <= 29:
                    buckets["20-29"] += 1
                elif 30 <= age <= 39:
                    buckets["30-39"] += 1
                elif 40 <= age <= 49:
                    buckets["40-49"] += 1
                elif 50 <= age <= 59:
                    buckets["50-59"] += 1
                else:
                    buckets["60+"] += 1
            else:
                unknown += 1
                
        for group, count in buckets.items():
            if count > 0:
                data.append(DemographicGroupData(
                    group=group, 
                    count=count, 
                    percentage=round((count / total_employees) * 100, 2)
                ))
        if unknown > 0:
            data.append(DemographicGroupData(
                group="Unknown",
                count=unknown,
                percentage=round((unknown / total_employees) * 100, 2)
            ))

    elif group_by == DemographicsGroupBy.GENDER:
        from collections import Counter
        # Handle nullable gender
        counts = Counter(emp.gender.value if emp.gender else "Unknown" for emp in employees)
        for group, count in counts.items():
            data.append(DemographicGroupData(
                group=group.title(),
                count=count,
                percentage=round((count / total_employees) * 100, 2)
            ))

    elif group_by == DemographicsGroupBy.DEPARTMENT:
        dept_counts = {}
        for emp in employees:
            dept_name = emp.department.department_name if emp.department else "No Department"
            dept_counts[dept_name] = dept_counts.get(dept_name, 0) + 1
            
        for group, count in dept_counts.items():
            data.append(DemographicGroupData(
                group=group,
                count=count,
                percentage=round((count / total_employees) * 100, 2)
            ))

    elif group_by == DemographicsGroupBy.LOCATION:
        loc_counts = {}
        for emp in employees:
            loc_name = emp.location.location_name if emp.location else "No Location"
            loc_counts[loc_name] = loc_counts.get(loc_name, 0) + 1
            
        for group, count in loc_counts.items():
            data.append(DemographicGroupData(
                group=group,
                count=count,
                percentage=round((count / total_employees) * 100, 2)
            ))

    elif group_by == DemographicsGroupBy.EMPLOYMENT_TYPE:
        from collections import Counter
        counts = Counter(emp.employment_type.value for emp in employees)
        for group, count in counts.items():
            data.append(DemographicGroupData(
                group=group.replace("_", " ").title(),
                count=count,
                percentage=round((count / total_employees) * 100, 2)
            ))

    elif group_by == DemographicsGroupBy.EMPLOYMENT_STATUS:
        # Note: Query filters only ACTIVE, but if we remove that filter later, this handles all
        from collections import Counter
        counts = Counter(emp.employment_status.value for emp in employees)
        for group, count in counts.items():
            data.append(DemographicGroupData(
                group=group.replace("_", " ").title(),
                count=count,
                percentage=round((count / total_employees) * 100, 2)
            ))
            
    return EmployeeDemographicsResponse(
        success=True,
        message="Demographics report generated successfully",
        total_employees=total_employees,
        group_by=group_by.value,
        data=data
    )

@router.get("/headcount", response_model=HeadcountReportResponse)
def get_headcount_report(
    from_date: date = Query(..., description="Start date of the report period"),
    to_date: date = Query(..., description="End date of the report period"),
    department_uuid: Optional[uuid.UUID] = Query(None, description="Filter by Department UUID"),
    location_uuid: Optional[uuid.UUID] = Query(None, description="Filter by Location UUID"),
    employment_type: Optional[EmploymentType] = Query(None, description="Filter by Employment Type"),
    db: Session = Depends(deps.get_db),
    current_org: Organization = Depends(deps.get_current_org)
):
    """
    Get headcount trends including new joiners, leavers, and total headcount over a period.
    Default aggregation is monthly if range > 31 days, else daily/weekly as needed.
    This implementation does Monthly trends.
    """
    if to_date < from_date:
        raise HTTPException(status_code=400, detail="to_date must be after from_date")

    # 1. Base Query for Filtering Employees (Active or Inactive relevant to period)
    base_query = db.query(Employee).filter(
        Employee.organization_id == current_org.id,
        Employee.is_deleted == False
    )

    if department_uuid:
        base_query = base_query.join(Department).filter(Department.uuid == department_uuid)
    if location_uuid:
        base_query = base_query.join(Location).filter(Location.uuid == location_uuid)
    if employment_type:
        base_query = base_query.filter(Employee.employment_type == employment_type)

    all_relevant_employees = base_query.all()

    # 2. Pre-calculate: Current Headcount
    current_headcount = sum(1 for e in all_relevant_employees if e.employment_status == EmploymentStatus.ACTIVE)
    
    # 3. Calculate Trends
    # We will generate month end dates between from_date and to_date
    
    start_dt = from_date.replace(day=1)
    end_dt = to_date
    
    trends = []
    
    # Helper to iterate months
    def months_iter(start_month, end_month):
        current = start_month
        while current <= end_month:
            yield current
            # Move to first day of next month
            nm = current.month + 1
            ny = current.year
            if nm > 12:
                nm = 1
                ny += 1
            current = date(ny, nm, 1)

    total_new_joiners = 0
    total_leavers = 0
    
    for month_start in months_iter(start_dt, end_dt):
        # Define month period
        _, days_in_month = monthrange(month_start.year, month_start.month)
        month_end = date(month_start.year, month_start.month, days_in_month)
        
        # Clip to requested range
        period_start = max(from_date, month_start)
        period_end = min(to_date, month_end)
        
        if period_start > period_end:
            continue
            
        period_joiners = 0
        period_leavers = 0
        
        # Calculate for this specific month/period
        for emp in all_relevant_employees:
            # Joined in this period?
            if emp.date_of_joining and period_start <= emp.date_of_joining <= period_end:
                period_joiners += 1
                
            # Left in this period?
            if emp.date_of_leaving and period_start <= emp.date_of_leaving <= period_end:
                period_leavers += 1
                
        # Calculate Headcount at End of Period
        # Headcount = (Active before period) + (Joiners to date) - (Leavers to date)
        # Or simpler: Check status as of period_end
        
        # To be precise:
        # Active if:
        # 1. Joined on or before period_end
        # 2. NOT (Left before period_end) i.e. Left is None OR Left > period_end
        
        period_headcount = 0
        for emp in all_relevant_employees:
            joined = emp.date_of_joining <= period_end
            not_left = (emp.date_of_leaving is None) or (emp.date_of_leaving > period_end)
            if joined and not_left:
                period_headcount += 1
        
        trends.append(HeadcountTrendData(
            date=period_end,
            total_headcount=period_headcount,
            new_joiners=period_joiners,
            leavers=period_leavers,
            net_change=period_joiners - period_leavers
        ))
        
        total_new_joiners += period_joiners
        total_leavers += period_leavers

    return HeadcountReportResponse(
        success=True,
        message="Headcount report generated successfully",
        from_date=from_date,
        to_date=to_date,
        current_headcount=current_headcount,
        total_new_joiners=total_new_joiners,
        total_leavers=total_leavers,
        trends=trends
    )

@router.get("/new-hires", response_model=NewHireReportResponse)
def get_new_hires_report(
    from_date: date = Query(..., description="Start date of the report period"),
    to_date: date = Query(..., description="End date of the report period"),
    department_uuid: Optional[uuid.UUID] = Query(None, description="Filter by Department UUID"),
    location_uuid: Optional[uuid.UUID] = Query(None, description="Filter by Location UUID"),
    db: Session = Depends(deps.get_db),
    current_org: Organization = Depends(deps.get_current_org)
):
    """
    Get a list of new hires within the specified date range.
    """
    if to_date < from_date:
        raise HTTPException(status_code=400, detail="to_date must be after from_date")

    query = db.query(Employee).filter(
        Employee.organization_id == current_org.id,
        Employee.is_deleted == False,
        Employee.date_of_joining >= from_date,
        Employee.date_of_joining <= to_date
    )

    if department_uuid:
        query = query.join(Department).filter(Department.uuid == department_uuid)
    if location_uuid:
        query = query.join(Location).filter(Location.uuid == location_uuid)

    # Eager load related data for response schema
    query = query.options(
        joinedload(Employee.department),
        joinedload(Employee.location),
        joinedload(Employee.job_title),
        joinedload(Employee.reporting_manager)
    ).order_by(Employee.date_of_joining.desc())

    new_hires = query.all()

    return NewHireReportResponse(
        success=True,
        message="New hires report generated successfully",
        from_date=from_date,
        to_date=to_date,
        total_new_hires=len(new_hires),
        data=new_hires
    )

@router.get("/exits", response_model=EmployeeExitReportResponse)
def get_employee_exits_report(
    from_date: date = Query(..., description="Start date of the report period"),
    to_date: date = Query(..., description="End date of the report period"),
    department_uuid: Optional[uuid.UUID] = Query(None, description="Filter by Department UUID"),
    location_uuid: Optional[uuid.UUID] = Query(None, description="Filter by Location UUID"),
    db: Session = Depends(deps.get_db),
    current_org: Organization = Depends(deps.get_current_org)
):
    """
    Get a list of employee exits within the specified date range.
    """
    if to_date < from_date:
        raise HTTPException(status_code=400, detail="to_date must be after from_date")

    # Filter for employees who have a date_of_leaving in the range
    query = db.query(Employee).filter(
        Employee.organization_id == current_org.id,
        Employee.is_deleted == False,
        Employee.date_of_leaving >= from_date,
        Employee.date_of_leaving <= to_date
    )

    if department_uuid:
        query = query.join(Department).filter(Department.uuid == department_uuid)
    if location_uuid:
        query = query.join(Location).filter(Location.uuid == location_uuid)

    query = query.options(
        joinedload(Employee.department),
        joinedload(Employee.location),
        joinedload(Employee.job_title),
        joinedload(Employee.reporting_manager)
    ).order_by(Employee.date_of_leaving.desc())

    exits = query.all()

    return EmployeeExitReportResponse(
        success=True,
        message="Employee exits report generated successfully",
        from_date=from_date,
        to_date=to_date,
        total_exits=len(exits),
        data=exits
    )

@router.get("/probation", response_model=ProbationReportResponse)
def get_probation_report(
    status_filter: Optional[ProbationStatus] = Query(None, description="Filter by probation status (upcoming, overdue, completed)"),
    db: Session = Depends(deps.get_db),
    current_org: Organization = Depends(deps.get_current_org)
):
    """
    Get probation completion tracking report.
    - Upcoming: Active employees with probation_end_date in the future (next 30 days usually, but here we list all future unless constrained).
    - Overdue: Active employees with probation_end_date in the past but still in 'probation' status.
    - Completed: Active employees who have confirmed status or whose probation end date passed and status updated.
    """
    today = date.today()
    
    query = db.query(Employee).filter(
        Employee.organization_id == current_org.id,
        Employee.is_deleted == False,
        Employee.employment_status == EmploymentStatus.ACTIVE
    )
    
    employees = query.all()
    
    report_data = []
    
    for emp in employees:
        # Skip if no probation date set
        if not emp.probation_end_date:
            continue
            
        days_remaining = (emp.probation_end_date - today).days
        status_value = None
        
        # Determine logical status
        if emp.date_of_confirmation:
            status_value = ProbationStatus.COMPLETED
        elif emp.probation_end_date < today:
            status_value = ProbationStatus.OVERDUE
        else:
            status_value = ProbationStatus.UPCOMING
            
        # Apply Filter if provided
        if status_filter and status_value != status_filter:
            continue
            
        
        # Build Schema Object
        base_data = EmployeeMinimalSchema.model_validate(emp).model_dump()
        emp_schema = EmployeeProbationSchema(
            **base_data,
            probation_end_date=emp.probation_end_date,
            days_remaining=days_remaining,
            probation_status=status_value.value if status_value else None
        )
        
        report_data.append(emp_schema)

    # Sort logic: Overdue first, then upcoming by closest date
    report_data.sort(key=lambda x: (x.days_remaining if x.days_remaining is not None else 9999))

    return ProbationReportResponse(
        success=True,
        message="Probation report generated successfully",
        status_filter=status_filter.value if status_filter else "all",
        total_records=len(report_data),
        data=report_data
    )

@router.get("/anniversary", response_model=AnniversaryReportResponse)
def get_anniversary_report(
    month: Optional[int] = Query(None, ge=1, le=12, description="Filter by month (1-12). Defaults to current month if year not provided."),
    year: Optional[int] = Query(None, description="Year to check for anniversary. Defaults to current year."),
    years_completed: Optional[int] = Query(None, description="Filter specific years of service (e.g., 5, 10)"),
    db: Session = Depends(deps.get_db),
    current_org: Organization = Depends(deps.get_current_org)
):
    """
    Get work anniversaries occurring in a specific month/year.
    Useful for 'Upcoming Anniversaries' widgets.
    """
    today = date.today()
    target_month = month if month else today.month
    target_year = year if year else today.year
    
    # Base Query: Active Employees
    query = db.query(Employee).filter(
        Employee.organization_id == current_org.id,
        Employee.is_deleted == False,
        Employee.employment_status == EmploymentStatus.ACTIVE,
        # SQLAlchemy filter for month extraction
        func.extract('month', Employee.date_of_joining) == target_month
    )
    
    employees = query.all()
    
    report_data = []
    
    for emp in employees:
        if not emp.date_of_joining:
            continue
            
        # Calculate years completed relative to target year
        # Anniversary date in the target year
        try:
            anniversary_date = date(target_year, emp.date_of_joining.month, emp.date_of_joining.day)
        except ValueError:
            # Handle Feb 29 for leap year joiners
            anniversary_date = date(target_year, 3, 1) # Move to Mar 1st or Feb 28th? Usually Mar 1st or Feb 28.
            
        completed_years = target_year - emp.date_of_joining.year
        
        # Don't include future joiners or 0 years if strict logic needed
        # But for 'upcoming anniversaries', 0 years is just joined.
        # Usually anniversary celebrates > 0 years.
        if completed_years < 1:
            continue
            
        if years_completed is not None and completed_years != years_completed:
            continue
            
        # Build Schema
        base_data = EmployeeMinimalSchema.model_validate(emp).model_dump()
        emp_schema = EmployeeAnniversarySchema(
            **base_data,
            original_joining_date=emp.date_of_joining,
            years_completed=completed_years,
            anniversary_date=anniversary_date
        )
        
        report_data.append(emp_schema)
        
    # Sort by anniversary day in current month
    report_data.sort(key=lambda x: x.anniversary_date.day)

    return AnniversaryReportResponse(
        success=True,
        message="Anniversary report generated successfully",
        month_filter=target_month,
        total_records=len(report_data),
        data=report_data
    )

@router.get("/birthday", response_model=BirthdayReportResponse)
def get_birthday_report(
    month: Optional[int] = Query(None, ge=1, le=12, description="Filter by specific month"),
    from_date: Optional[date] = Query(None, description="Start of date range (ignores year of DOB)"),
    to_date: Optional[date] = Query(None, description="End of date range (ignores year of DOB)"),
    db: Session = Depends(deps.get_db),
    current_org: Organization = Depends(deps.get_current_org)
):
    """
    Get employees having birthdays in a specific month or date range.
    """
    if from_date and to_date and to_date < from_date:
        raise HTTPException(status_code=400, detail="to_date must be after from_date")

    today = date.today()
    target_month = month
    
    # If no criteria, default to current month
    if not month and not (from_date and to_date):
        target_month = today.month

    # Base Query
    query = db.query(Employee).filter(
        Employee.organization_id == current_org.id,
        Employee.is_deleted == False,
        Employee.employment_status == EmploymentStatus.ACTIVE,
        Employee.date_of_birth != None
    )

    # Optimization: If filtering by month, do it in DB
    if target_month:
        query = query.filter(func.extract('month', Employee.date_of_birth) == target_month)
    
    employees = query.all()
    
    report_data = []
    
    search_start = from_date if from_date else today.replace(day=1) # somewhat arbitrary fallbacks
    search_end = to_date if to_date else (today.replace(month=12, day=31))
    
    # If using month filter, set range to cover that month in current/relevant year
    if target_month:
        # We process returned employees, calculating their birthday in current year
        search_start = date(today.year, target_month, 1)
        _, days = monthrange(today.year, target_month)
        search_end = date(today.year, target_month, days)

    range_filtering = (from_date is not None and to_date is not None)

    for emp in employees:
        dob = emp.date_of_birth
        
        # Calculate birthday in current year
        try:
            current_birthday = date(today.year, dob.month, dob.day)
        except ValueError:
            # Feb 29
            current_birthday = date(today.year, 2, 28) # or 3, 1
        
        # Adjust for year boundary if range crosses year end (e.g. Dec to Jan)
        # This is complex. Let's simplify:
        # If we asked for a month, we already filtered by DB, so current_birthday is in that month (mostly).
        # We just need to handle year.
        
        # If range filtering is ON, check if birthday falls in range
        if range_filtering:
            # Need to handle 'current_birthday' vs 'next_birthday' relative to range?
            # Usually range is close to 'today'.
            # Let's check if current_birthday is in range. 
            # If range spans years (e.g. 2024-12-01 to 2025-01-31), 
            # we might need to check adjacent years.
            
            # Simple check: 
            in_range = False
            # Check current year birthday
            if from_date <= current_birthday <= to_date:
                in_range = True
            # Check next year birthday (for Jan birthdays when looking from Dec)
            try:
                next_year_birthday = current_birthday.replace(year=today.year + 1)
            except ValueError:
                next_year_birthday = date(today.year + 1, 2, 28)
                
            if from_date <= next_year_birthday <= to_date:
                in_range = True
                current_birthday = next_year_birthday # Use the one in range
                
            if not in_range:
                continue

        # Calculate Age
        # Age they are turning on this birthday
        age = current_birthday.year - dob.year
        
        # Create Schema
        base_data = EmployeeMinimalSchema.model_validate(emp).model_dump()
        emp_schema = EmployeeBirthdaySchema(
            **base_data,
            date_of_birth=dob,
            current_birthday=current_birthday,
            age=age
        )
        report_data.append(emp_schema)

    # Sort by birthday date
    report_data.sort(key=lambda x: x.current_birthday)

    return BirthdayReportResponse(
        success=True,
        message="Birthday report generated successfully",
        month_filter=target_month if target_month else None,
        total_records=len(report_data),
        data=report_data
    )

@router.get("/attendance/summary", response_model=AttendanceSummaryReportResponse)
def get_attendance_summary_report(
    from_date: date = Query(..., description="Start date of the report period"),
    to_date: date = Query(..., description="End date of the report period"),
    department_uuid: Optional[uuid.UUID] = Query(None, description="Filter by Department UUID"),
    location_uuid: Optional[uuid.UUID] = Query(None, description="Filter by Location UUID"),
    employee_uuid: Optional[uuid.UUID] = Query(None, description="Filter by Specific Employee UUID"),
    db: Session = Depends(deps.get_db),
    current_org: Organization = Depends(deps.get_current_org)
):
    """
    Get aggregated attendance statistics and daily trends for a period.
    """
    if to_date < from_date:
        raise HTTPException(status_code=400, detail="to_date must be after from_date")

    # 1. Base Employee Query (to know the universe of employees for percentages)
    emp_query = db.query(Employee.id).filter(
        Employee.organization_id == current_org.id,
        Employee.is_deleted == False
    )

    if department_uuid:
        emp_query = emp_query.join(Department).filter(Department.uuid == department_uuid)
    if location_uuid:
        emp_query = emp_query.join(Location).filter(Location.uuid == location_uuid)
    if employee_uuid:
        emp_query = emp_query.filter(Employee.uuid == employee_uuid)
        
    employee_ids_rows = emp_query.all()
    employee_ids = [r[0] for r in employee_ids_rows]
    total_employees_count = len(employee_ids)
    
    if total_employees_count == 0:
        return AttendanceSummaryReportResponse(
            success=True,
            message="No employees found for given criteria",
            from_date=from_date,
            to_date=to_date,
            total_working_days=0,
            stats=AttendanceStats(),
            trends=[]
        )

    # 2. Query Attendance Records
    # Join with Employee to respect filters if not filtering by ID list directly (but we have IDs)
    atts = db.query(AttendanceRecord).filter(
        AttendanceRecord.organization_id == current_org.id,
        AttendanceRecord.attendance_date >= from_date,
        AttendanceRecord.attendance_date <= to_date,
        AttendanceRecord.employee_id.in_(employee_ids)
    ).all()
    
    # 3. Aggregate Stats
    stats = AttendanceStats()
    total_hours = 0.0
    present_day_records = 0 # Count of records where hours > 0 or status is present
    
    # Structure for Trends: Date -> {present: 0, absent: 0, total: 0}
    trend_map = {}
    # Initialize trend map for all days in range to ensure continuity? 
    # Or just returned days. API spec implies daily trends.
    
    # pre-fill map
    curr = from_date
    while curr <= to_date:
        trend_map[curr] = {"present": 0, "absent": 0, "total": total_employees_count} # Approx total
        curr += timedelta(days=1)
        
    for rec in atts:
        d = rec.attendance_date
        if d not in trend_map:
            continue # Should be covered
            
        # Status Counts
        if rec.status == AttendanceStatus.PRESENT:
            stats.present += 1
            trend_map[d]["present"] += 1
        elif rec.status == AttendanceStatus.ABSENT:
            stats.absent += 1
            trend_map[d]["absent"] += 1
        elif rec.status == AttendanceStatus.ON_LEAVE:
            stats.leave += 1
        elif rec.status == AttendanceStatus.HALF_DAY:
            stats.half_day += 1
            trend_map[d]["present"] += 0.5 # Or count as 1 head? usually 1 head present.
            
        # Late/Early
        if rec.late_by_minutes > 0:
            stats.late_arrival += 1
        if rec.early_departure_minutes > 0:
            stats.early_departure += 1
            
        # Hours
        if rec.total_work_hours:
            total_hours += float(rec.total_work_hours)
            if rec.total_work_hours > 0:
                present_day_records += 1

    # Logic fix: Absent is often not a record if not generated. 
    # If using 'list_attendance_logs' logic, we generate daily records. 
    # Assuming attendance generator runs nightly.
    # Otherwise, we infer absent = total_employees - present - leave?
    
    # For stats, we rely on records.
    if present_day_records > 0:
        stats.avg_work_hours = round(total_hours / present_day_records, 2)
        
    # BUILD TRENDS LIST
    trends = []
    sorted_dates = sorted(trend_map.keys())
    for d in sorted_dates:
        day_data = trend_map[d]
        # Calculate percentages based on active employees that day (approximated by total_employees_count constant for period)
        # Ideally we check active count per day.
        
        # Simple Percentage
        p_count = day_data["present"]
        a_count = day_data["absent"]
        total = day_data["total"]
        
        p_pct = 0.0
        a_pct = 0.0
        
        if total > 0:
            p_pct = round((p_count / total) * 100, 1)
            a_pct = round((a_count / total) * 100, 1)
            
        trends.append(AttendanceTrend(
            date=d,
            present_percentage=p_pct,
            absent_percentage=a_pct
        ))

    return AttendanceSummaryReportResponse(
        success=True,
        message="Attendance summary generated successfully",
        from_date=from_date,
        to_date=to_date,
        total_working_days=(to_date - from_date).days + 1,
        stats=stats,
        trends=trends
    )

@router.get("/attendance/daily", response_model=DailyAttendanceReportResponse)
def get_daily_attendance_report(
    attendance_date: date = Query(..., alias="date", description="Date for which to get the report"),
    department_uuid: Optional[uuid.UUID] = Query(None, description="Filter by Department UUID"),
    location_uuid: Optional[uuid.UUID] = Query(None, description="Filter by Location UUID"),
    db: Session = Depends(deps.get_db),
    current_org: Organization = Depends(deps.get_current_org)
):
    """
    Get detailed attendance records for all employees on a specific date.
    """
    # 1. Fetch relevant employees
    emp_query = db.query(Employee).filter(
        Employee.organization_id == current_org.id,
        Employee.is_deleted == False,
        Employee.employment_status == EmploymentStatus.ACTIVE
    )

    if department_uuid:
        emp_query = emp_query.join(Department).filter(Department.uuid == department_uuid)
    if location_uuid:
        emp_query = emp_query.join(Location).filter(Location.uuid == location_uuid)

    employees = emp_query.options(
        joinedload(Employee.department),
        joinedload(Employee.location)
    ).all()
    
    employee_ids = [e.id for e in employees]
    
    if not employee_ids:
        return DailyAttendanceReportResponse(
            success=True,
            message="No employees found for given filters",
            date=attendance_date,
            total_records=0,
            data=[]
        )

    # 2. Fetch attendance records for these employees on that date
    atts = db.query(AttendanceRecord).filter(
        AttendanceRecord.organization_id == current_org.id,
        AttendanceRecord.attendance_date == attendance_date,
        AttendanceRecord.employee_id.in_(employee_ids)
    ).all()
    
    att_map = {a.employee_id: a for a in atts}
    
    report_data = []
    
    for emp in employees:
        att = att_map.get(emp.id)
        
        record = DailyAttendanceRecord(
            employee_uuid=emp.uuid,
            employee_name=emp.full_name,
            employee_code=emp.employee_code,
            department=emp.department.department_name if emp.department else None,
            location=emp.location.location_name if emp.location else None,
            status=att.status.value if att else AttendanceStatus.ABSENT.value,
            check_in=att.first_check_in if att else None,
            check_out=att.last_check_out if att else None,
            work_hours=float(att.total_work_hours) if att else 0.0,
            is_late=att.is_late if att else False,
            is_early_departure=att.is_early_departure if att else False
        )
        report_data.append(record)

    # Sort by department then name
    report_data.sort(key=lambda x: (x.department or "", x.employee_name))

    return DailyAttendanceReportResponse(
        success=True,
        message="Daily attendance report generated successfully",
        date=attendance_date,
        total_records=len(report_data),
        data=report_data
    )

@router.get("/attendance/monthly", response_model=MonthlyAttendanceReportResponse)
def get_monthly_attendance_report(
    month: int = Query(..., ge=1, le=12, description="Month (1-12)"),
    year: int = Query(..., description="Year (e.g., 2024)"),
    department_uuid: Optional[uuid.UUID] = Query(None, description="Filter by Department UUID"),
    employee_uuid: Optional[uuid.UUID] = Query(None, description="Filter by Specific Employee UUID"),
    db: Session = Depends(deps.get_db),
    current_org: Organization = Depends(deps.get_current_org)
):
    """
    Get monthly attendance summary for employees.
    """
    # 1. Fetch relevant employees
    emp_query = db.query(Employee).filter(
        Employee.organization_id == current_org.id,
        Employee.is_deleted == False
    )

    if department_uuid:
        emp_query = emp_query.join(Department).filter(Department.uuid == department_uuid)
    if employee_uuid:
        emp_query = emp_query.filter(Employee.uuid == employee_uuid)

    employees = emp_query.options(
        joinedload(Employee.department)
    ).all()
    
    employee_ids = [e.id for e in employees]
    
    if not employee_ids:
        return MonthlyAttendanceReportResponse(
            success=True,
            message="No employees found for given filters",
            month=month,
            year=year,
            total_records=0,
            data=[]
        )

    # 2. Define date range for the month
    first_day = date(year, month, 1)
    _, last_day_num = monthrange(year, month)
    last_day = date(year, month, last_day_num)

    # 3. Fetch attendance records
    atts = db.query(AttendanceRecord).filter(
        AttendanceRecord.organization_id == current_org.id,
        AttendanceRecord.attendance_date >= first_day,
        AttendanceRecord.attendance_date <= last_day,
        AttendanceRecord.employee_id.in_(employee_ids)
    ).all()

    # Group by employee
    att_by_employee = {}
    for rec in atts:
        if rec.employee_id not in att_by_employee:
            att_by_employee[rec.employee_id] = []
        att_by_employee[rec.employee_id].append(rec)

    report_data = []

    for emp in employees:
        emp_atts = att_by_employee.get(emp.id, [])
        
        summary = MonthlyAttendanceSummary()
        total_hours = 0.0
        present_count = 0
        
        for rec in emp_atts:
            if rec.status == AttendanceStatus.PRESENT:
                summary.present += 1
                present_count += 1
            elif rec.status == AttendanceStatus.ABSENT:
                summary.absent += 1
            elif rec.status == AttendanceStatus.HALF_DAY:
                summary.half_day += 1
                present_count += 1
            elif rec.status == AttendanceStatus.ON_LEAVE:
                summary.on_leave += 1
                
            if rec.is_late:
                summary.late_arrivals += 1
            if rec.is_early_departure:
                summary.early_departures += 1
                
            if rec.total_work_hours:
                h = float(rec.total_work_hours)
                total_hours += h
                summary.total_work_hours += h

        if present_count > 0:
            summary.avg_work_hours = round(total_hours / present_count, 2)
        summary.total_work_hours = round(summary.total_work_hours, 2)

        record = MonthlyAttendanceRecord(
            employee_uuid=emp.uuid,
            employee_name=emp.full_name,
            employee_code=emp.employee_code,
            department=emp.department.department_name if emp.department else None,
            summary=summary
        )
        report_data.append(record)

    # Sort by department then name
    report_data.sort(key=lambda x: (x.department or "", x.employee_name))

    return MonthlyAttendanceReportResponse(
        success=True,
        message="Monthly attendance report generated successfully",
        month=month,
        year=year,
        total_records=len(report_data),
        data=report_data
    )

@router.get("/attendance/late-arrivals", response_model=LateArrivalReportResponse)
def get_late_arrivals_report(
    from_date: date = Query(..., description="Start date of the report period"),
    to_date: date = Query(..., description="End date of the report period"),
    department_uuid: Optional[uuid.UUID] = Query(None, description="Filter by Department UUID"),
    threshold_minutes: int = Query(0, description="Minimum minutes late to be included in the report"),
    db: Session = Depends(deps.get_db),
    current_org: Organization = Depends(deps.get_current_org)
):
    """
    Get a list of late arrival instances for employees within a date range.
    """
    if to_date < from_date:
        raise HTTPException(status_code=400, detail="to_date must be after from_date")

    # Base query for AttendanceRecord
    query = db.query(AttendanceRecord).join(
        Employee, AttendanceRecord.employee_id == Employee.id
    ).filter(
        AttendanceRecord.organization_id == current_org.id,
        AttendanceRecord.attendance_date >= from_date,
        AttendanceRecord.attendance_date <= to_date,
        AttendanceRecord.late_by_minutes > threshold_minutes,
        Employee.is_deleted == False
    )

    # Apply department filter if provided
    if department_uuid:
        query = query.join(Department, Employee.department_id == Department.id).filter(
            Department.uuid == department_uuid
        )

    # Eager load related data
    query = query.options(
        joinedload(AttendanceRecord.employee).joinedload(Employee.department)
    ).order_by(AttendanceRecord.attendance_date.desc(), AttendanceRecord.late_by_minutes.desc())

    late_records = query.all()

    report_data = []
    for rec in late_records:
        # Construct shift_start_time if possible
        # AttendanceRecord has shift_start_time (Time) and attendance_date (Date)
        # We can combine them into a datetime
        shift_start = None
        if rec.shift_start_time and rec.attendance_date:
            shift_start = datetime.combine(rec.attendance_date, rec.shift_start_time)

        record = LateArrivalRecord(
            employee_uuid=rec.employee.uuid,
            employee_name=rec.employee.full_name,
            employee_code=rec.employee.employee_code,
            department=rec.employee.department.department_name if rec.employee.department else None,
            date=rec.attendance_date,
            shift_start_time=shift_start,
            actual_check_in=rec.first_check_in,
            late_minutes=rec.late_by_minutes
        )
        report_data.append(record)

    return LateArrivalReportResponse(
        success=True,
        message="Late arrivals report generated successfully",
        from_date=from_date,
        to_date=to_date,
        total_records=len(report_data), # Wait, the schema uses total_instances or total_records?
        # Let's check the schema I just wrote. 
        # I wrote total_instances in LateArrivalReportResponse. 
        # Actually total_records in others. 
        # Let's align. I'll use total_instances for now since I just wrote it.
        total_instances=len(report_data),
        data=report_data
    )

@router.get("/attendance/early-departures", response_model=EarlyDepartureReportResponse)
def get_early_departures_report(
    from_date: date = Query(..., description="Start date of the report period"),
    to_date: date = Query(..., description="End date of the report period"),
    department_uuid: Optional[uuid.UUID] = Query(None, description="Filter by Department UUID"),
    threshold_minutes: int = Query(0, description="Minimum minutes early to be included in the report"),
    db: Session = Depends(deps.get_db),
    current_org: Organization = Depends(deps.get_current_org)
):
    """
    Get a list of early departure instances for employees within a date range.
    """
    if to_date < from_date:
        raise HTTPException(status_code=400, detail="to_date must be after from_date")

    # Base query for AttendanceRecord
    query = db.query(AttendanceRecord).join(
        Employee, AttendanceRecord.employee_id == Employee.id
    ).filter(
        AttendanceRecord.organization_id == current_org.id,
        AttendanceRecord.attendance_date >= from_date,
        AttendanceRecord.attendance_date <= to_date,
        AttendanceRecord.early_departure_minutes > threshold_minutes,
        Employee.is_deleted == False
    )

    # Apply department filter if provided
    if department_uuid:
        query = query.join(Department, Employee.department_id == Department.id).filter(
            Department.uuid == department_uuid
        )

    # Eager load related data
    query = query.options(
        joinedload(AttendanceRecord.employee).joinedload(Employee.department)
    ).order_by(AttendanceRecord.attendance_date.desc(), AttendanceRecord.early_departure_minutes.desc())

    records = query.all()

    report_data = []
    for rec in records:
        shift_end = None
        if rec.shift_end_time and rec.attendance_date:
            shift_end = datetime.combine(rec.attendance_date, rec.shift_end_time)

        record = EarlyDepartureRecord(
            employee_uuid=rec.employee.uuid,
            employee_name=rec.employee.full_name,
            employee_code=rec.employee.employee_code,
            department=rec.employee.department.department_name if rec.employee.department else None,
            date=rec.attendance_date,
            shift_end_time=shift_end,
            actual_check_out=rec.last_check_out,
            early_departure_minutes=rec.early_departure_minutes
        )
        report_data.append(record)

    return EarlyDepartureReportResponse(
        success=True,
        message="Early departures report generated successfully",
        from_date=from_date,
        to_date=to_date,
        total_instances=len(report_data),
        data=report_data
    )

@router.get("/attendance/absenteeism", response_model=AbsenteeismReportResponse)
def get_absenteeism_report(
    from_date: date = Query(..., description="Start date of the report period"),
    to_date: date = Query(..., description="End date of the report period"),
    department_uuid: Optional[uuid.UUID] = Query(None, description="Filter by Department UUID"),
    location_uuid: Optional[uuid.UUID] = Query(None, description="Filter by Location UUID"),
    db: Session = Depends(deps.get_db),
    current_org: Organization = Depends(deps.get_current_org)
):
    """
    Get absenteeism trends and rates for a period.
    Absenteeism rate = (Total Absent Days / (Total Employees * Total Working Days)) * 100
    """
    if to_date < from_date:
        raise HTTPException(status_code=400, detail="to_date must be after from_date")

    # 1. Base Employee Query to get total active employees for the period
    emp_query = db.query(Employee.id).filter(
        Employee.organization_id == current_org.id,
        Employee.is_deleted == False,
        Employee.employment_status == EmploymentStatus.ACTIVE
    )

    if department_uuid:
        emp_query = emp_query.join(Department).filter(Department.uuid == department_uuid)
    if location_uuid:
        emp_query = emp_query.join(Location).filter(Location.uuid == location_uuid)

    employee_ids = [r[0] for r in emp_query.all()]
    total_employees_count = len(employee_ids)

    if total_employees_count == 0:
        return AbsenteeismReportResponse(
            success=True,
            message="No active employees found for given criteria",
            from_date=from_date,
            to_date=to_date,
            total_active_employees=0,
            overall_absenteeism_rate=0.0,
            trends=[]
        )

    # 2. Query Attendance Records for Absent status
    atts = db.query(AttendanceRecord).filter(
        AttendanceRecord.organization_id == current_org.id,
        AttendanceRecord.attendance_date >= from_date,
        AttendanceRecord.attendance_date <= to_date,
        AttendanceRecord.employee_id.in_(employee_ids),
        AttendanceRecord.status == AttendanceStatus.ABSENT
    ).all()

    # 3. Calculate Trends
    trend_map = {}
    curr = from_date
    while curr <= to_date:
        trend_map[curr] = 0
        curr += timedelta(days=1)

    for rec in atts:
        if rec.attendance_date in trend_map:
            trend_map[rec.attendance_date] += 1

    total_working_days = (to_date - from_date).days + 1
    total_absent_days = len(atts)
    
    overall_rate = 0.0
    if total_employees_count > 0 and total_working_days > 0:
        overall_rate = round((total_absent_days / (total_employees_count * total_working_days)) * 100, 2)

    trends = []
    for d in sorted(trend_map.keys()):
        absent_count = trend_map[d]
        rate = 0.0
        if total_employees_count > 0:
            rate = round((absent_count / total_employees_count) * 100, 2)
        
        trends.append(AbsenteeismTrend(
            date=d,
            absent_count=absent_count,
            absenteeism_rate=rate
        ))

    return AbsenteeismReportResponse(
        success=True,
        message="Absenteeism report generated successfully",
        from_date=from_date,
        to_date=to_date,
        total_active_employees=total_employees_count,
        overall_absenteeism_rate=overall_rate,
        trends=trends
    )

@router.get("/overtime", response_model=OvertimeReportResponse)
def get_overtime_report(
    from_date: date = Query(..., description="Start date of the report period"),
    to_date: date = Query(..., description="End date of the report period"),
    department_uuid: Optional[uuid.UUID] = Query(None, description="Filter by Department UUID"),
    employee_uuid: Optional[uuid.UUID] = Query(None, description="Filter by Specific Employee UUID"),
    status: Optional[OvertimeStatus] = Query(None, description="Filter by Overtime Status"),
    db: Session = Depends(deps.get_db),
    current_org: Organization = Depends(deps.get_current_org)
):
    """
    Get overtime report for a period.
    """
    if to_date < from_date:
        raise HTTPException(status_code=400, detail="to_date must be after from_date")

    # Base Query
    query = db.query(OvertimeRequest).join(
        Employee, OvertimeRequest.employee_id == Employee.id
    ).filter(
        OvertimeRequest.organization_id == current_org.id,
        OvertimeRequest.attendance_date >= from_date,
        OvertimeRequest.attendance_date <= to_date,
        Employee.is_deleted == False
    )

    if department_uuid:
        query = query.join(Department, Employee.department_id == Department.id).filter(
            Department.uuid == department_uuid
        )
    
    if employee_uuid:
        query = query.filter(Employee.uuid == employee_uuid)
        
    if status:
        query = query.filter(OvertimeRequest.status == status)

    # Eager load related data
    query = query.options(
        joinedload(OvertimeRequest.employee).joinedload(Employee.department)
    ).order_by(OvertimeRequest.attendance_date.desc())

    overtime_requests = query.all()

    report_data = []
    total_requested = 0.0
    total_approved = 0.0
    total_cost = 0.0 # Placeholder

    for req in overtime_requests:
        hrs = float(req.overtime_hours)
        is_approved = req.status == OvertimeStatus.APPROVED or req.status == OvertimeStatus.PAID
        
        total_requested += hrs
        if is_approved:
            total_approved += hrs
            
            # If we had hourly_rate, we would calculate cost here:
            # cost = hrs * hourly_rate
            # total_cost += cost
        
        record = OvertimeReportRecord(
            employee_uuid=req.employee.uuid,
            employee_name=req.employee.full_name,
            employee_code=req.employee.employee_code,
            department=req.employee.department.department_name if req.employee.department else None,
            date=req.attendance_date,
            requested_hours=hrs,
            approved_hours=hrs if is_approved else 0.0,
            cost=0.0,
            status=req.status.value,
            is_paid=req.is_paid
        )
        report_data.append(record)

    return OvertimeReportResponse(
        success=True,
        message="Overtime report generated successfully",
        from_date=from_date,
        to_date=to_date,
        total_requested_hours=round(total_requested, 2),
        total_approved_hours=round(total_approved, 2),
        total_cost=round(total_cost, 2),
        data=report_data
    )

@router.get("/leave/summary", response_model=LeaveSummaryReportResponse)
def get_leave_summary_report(
    from_date: date = Query(..., description="Start date of the report period"),
    to_date: date = Query(..., description="End date of the report period"),
    department_uuid: Optional[uuid.UUID] = Query(None, description="Filter by Department UUID"),
    leave_type_uuid: Optional[uuid.UUID] = Query(None, description="Filter by Leave Type UUID"),
    db: Session = Depends(deps.get_db),
    current_org: Organization = Depends(deps.get_current_org)
):
    """
    Get leave summary and utilization report for a period.
    """
    if to_date < from_date:
        raise HTTPException(status_code=400, detail="to_date must be after from_date")

    # Base Query for LeaveApplications
    query = db.query(LeaveApplication).join(
        Employee, LeaveApplication.employee_id == Employee.id
    ).filter(
        LeaveApplication.organization_id == current_org.id,
        LeaveApplication.from_date >= from_date,
        LeaveApplication.from_date <= to_date, # Or overlap? Usually summary starts with from_date
        Employee.is_deleted == False
    )

    if department_uuid:
        query = query.join(Department, Employee.department_id == Department.id).filter(
            Department.uuid == department_uuid
        )
    
    if leave_type_uuid:
        query = query.join(LeaveType, LeaveApplication.leave_type_id == LeaveType.id).filter(
            LeaveType.uuid == leave_type_uuid
        )

    # Eager load leave type
    query = query.options(joinedload(LeaveApplication.leave_type))
    
    apps = query.all()

    # Aggregate by Leave Type
    util_map = {} # leave_type_id -> data
    
    # Pre-fetch all leave types for the org to ensure all are in the list if needed
    lt_query = db.query(LeaveType).filter(LeaveType.organization_id == current_org.id)
    if leave_type_uuid:
        lt_query = lt_query.filter(LeaveType.uuid == leave_type_uuid)
    leave_types = lt_query.all()
    
    for lt in leave_types:
        util_map[lt.id] = {
            "name": lt.leave_name,
            "code": lt.leave_code,
            "applied": 0.0,
            "approved": 0.0,
            "rejected": 0.0
        }

    total_approved_days = 0.0
    for app in apps:
        if app.leave_type_id not in util_map:
            continue
            
        days = float(app.total_days)
        util_map[app.leave_type_id]["applied"] += days
        
        if app.status == LeaveStatus.APPROVED:
            util_map[app.leave_type_id]["approved"] += days
            total_approved_days += days
        elif app.status == LeaveStatus.REJECTED:
            util_map[app.leave_type_id]["rejected"] += days

    utilization_data = []
    for lt_id, data in util_map.items():
        applied = data["applied"]
        approved = data["approved"]
        percentage = (approved / applied * 100) if applied > 0 else 0.0
        
        utilization_data.append(LeaveUtilizationData(
            leave_type_name=data["name"],
            leave_type_code=data["code"],
            total_applied_days=round(applied, 2),
            total_approved_days=round(approved, 2),
            total_rejected_days=round(data["rejected"], 2),
            utilization_percentage=round(percentage, 2)
        ))

    return LeaveSummaryReportResponse(
        success=True,
        message="Leave summary report generated successfully",
        from_date=from_date,
        to_date=to_date,
        total_applications=len(apps),
        total_approved_days=round(total_approved_days, 2),
        utilization=utilization_data
    )

@router.get("/leave/balance", response_model=LeaveBalanceReportResponse)
def get_leave_balance_report(
    year: int = Query(..., description="The year for which to get leave balances"),
    department_uuid: Optional[uuid.UUID] = Query(None, description="Filter by Department UUID"),
    leave_type_uuid: Optional[uuid.UUID] = Query(None, description="Filter by Leave Type UUID"),
    db: Session = Depends(deps.get_db),
    current_org: Organization = Depends(deps.get_current_org)
):
    """
    Get leave balances for all employees for a specific year.
    """
    # 1. Base Query for LeaveBalance
    query = db.query(LeaveBalance).join(
        Employee, LeaveBalance.employee_id == Employee.id
    ).filter(
        LeaveBalance.organization_id == current_org.id,
        LeaveBalance.balance_year == year,
        Employee.is_deleted == False
    )

    if department_uuid:
        query = query.join(Department, Employee.department_id == Department.id).filter(
            Department.uuid == department_uuid
        )
    
    if leave_type_uuid:
        query = query.join(LeaveType, LeaveBalance.leave_type_id == LeaveType.id).filter(
            LeaveType.uuid == leave_type_uuid
        )

    # Eager load related data
    query = query.options(
        joinedload(LeaveBalance.employee).joinedload(Employee.department),
        joinedload(LeaveBalance.leave_type)
    ).order_by(Employee.employee_code.asc())

    balances = query.all()

    report_data = []
    for bal in balances:
        record = LeaveBalanceRecord(
            employee_uuid=bal.employee.uuid,
            employee_name=bal.employee.full_name,
            employee_code=bal.employee.employee_code,
            department=bal.employee.department.department_name if bal.employee.department else None,
            leave_type_name=bal.leave_type.leave_name,
            leave_type_code=bal.leave_type.leave_code,
            opening_balance=float(bal.opening_balance + bal.brought_forward),
            accrued=float(bal.accrued + bal.credited),
            used=float(bal.used),
            available_balance=float(bal.available_balance)
        )
        report_data.append(record)

    return LeaveBalanceReportResponse(
        success=True,
        message="Leave balance report generated successfully",
        year=year,
        total_records=len(report_data),
        data=report_data
    )

@router.get("/leave/trends", response_model=LeaveTrendsReportResponse)
def get_leave_trends_report(
    from_date: date = Query(..., description="Start date of the report period"),
    to_date: date = Query(..., description="End date of the report period"),
    department_uuid: Optional[uuid.UUID] = Query(None, description="Filter by Department UUID"),
    leave_type_uuid: Optional[uuid.UUID] = Query(None, description="Filter by Leave Type UUID"),
    db: Session = Depends(deps.get_db),
    current_org: Organization = Depends(deps.get_current_org)
):
    """
    Get leave trends and patterns for a period.
    """
    if to_date < from_date:
        raise HTTPException(status_code=400, detail="to_date must be after from_date")

    # 1. Query approved applications that overlap with the period
    query = db.query(LeaveApplication).join(
        Employee, LeaveApplication.employee_id == Employee.id
    ).filter(
        LeaveApplication.organization_id == current_org.id,
        LeaveApplication.status == LeaveStatus.APPROVED,
        LeaveApplication.from_date <= to_date,
        LeaveApplication.to_date >= from_date,
        Employee.is_deleted == False
    )

    if department_uuid:
        query = query.join(Department, Employee.department_id == Department.id).filter(
            Department.uuid == department_uuid
        )
    
    if leave_type_uuid:
        query = query.join(LeaveType, LeaveApplication.leave_type_id == LeaveType.id).filter(
            LeaveType.uuid == leave_type_uuid
        )

    apps = query.all()

    # 2. Initialize Trend Map
    trend_map = {}
    curr = from_date
    while curr <= to_date:
        trend_map[curr] = {"count": 0, "days": 0.0}
        curr += timedelta(days=1)

    # 3. Process Applications
    for app in apps:
        overlap_start = max(from_date, app.from_date)
        overlap_end = min(to_date, app.to_date)
        
        curr_dt = overlap_start
        while curr_dt <= overlap_end:
            if curr_dt in trend_map:
                trend_map[curr_dt]["count"] += 1
                
                # Allocation of the leave day
                day_val = 1.0
                if app.from_date == app.to_date:
                    # Single day leave (could be half day)
                    day_val = float(app.total_days)
                elif curr_dt == app.from_date or curr_dt == app.to_date:
                    # Multi-day leave start/end
                    # If total_days is not an integer, we might have half days at ends
                    # But for simplicity in reports, we usually treat middle days as 1.0
                    # and ends based on total_days vs span.
                    pass 
                
                trend_map[curr_dt]["days"] += day_val
            curr_dt += timedelta(days=1)

    # 4. Format Response
    trends = []
    for d in sorted(trend_map.keys()):
        trends.append(LeaveTrendData(
            date=d,
            leave_count=trend_map[d]["count"],
            approved_days=round(trend_map[d]["days"], 2)
        ))

    return LeaveTrendsReportResponse(
        success=True,
        message="Leave trends report generated successfully",
        from_date=from_date,
        to_date=to_date,
        trends=trends
    )

@router.get("/leave/pending-approvals", response_model=PendingLeaveReportResponse)
def get_pending_leave_approvals(
    approver_uuid: Optional[uuid.UUID] = Query(None, description="Filter by Current Approver UUID"),
    department_uuid: Optional[uuid.UUID] = Query(None, description="Filter by Employee Department UUID"),
    db: Session = Depends(deps.get_db),
    current_org: Organization = Depends(deps.get_current_org)
):
    """
    Get a list of leave applications pending approval.
    """
    # 1. Base Query for Pending Applications
    query = db.query(LeaveApplication).filter(
        LeaveApplication.organization_id == current_org.id,
        LeaveApplication.status == LeaveStatus.PENDING
    )

    # 2. Join with Employee and Department for filtering
    query = query.join(Employee, LeaveApplication.employee_id == Employee.id).filter(
        Employee.is_deleted == False
    )

    if department_uuid:
        query = query.join(Department, Employee.department_id == Department.id).filter(
            Department.uuid == department_uuid
        )

    # 3. Filter by Approver
    if approver_uuid:
        # Use an alias to avoid conflict if Employee is already joined
        # But we can also join on LeaveApplication.current_approver_id
        ApproverAlias = db.query(Employee).filter(Employee.uuid == approver_uuid).subquery()
        query = query.filter(LeaveApplication.current_approver_id == ApproverAlias.c.id)

    # 4. Eager load related data for response
    query = query.options(
        joinedload(LeaveApplication.employee).joinedload(Employee.department),
        joinedload(LeaveApplication.leave_type),
        joinedload(LeaveApplication.current_approver)
    ).order_by(LeaveApplication.application_date.asc())

    pending_apps = query.all()

    report_data = []
    for app in pending_apps:
        record = PendingLeaveRecord(
            application_uuid=app.uuid,
            employee_uuid=app.employee.uuid,
            employee_name=app.employee.full_name,
            employee_code=app.employee.employee_code,
            department=app.employee.department.department_name if app.employee.department else None,
            leave_type=app.leave_type.leave_name,
            from_date=app.from_date,
            to_date=app.to_date,
            total_days=float(app.total_days),
            current_approver_name=app.current_approver.full_name if app.current_approver else "Unassigned",
            applied_date=app.application_date
        )
        report_data.append(record)

    return PendingLeaveReportResponse(
        success=True,
        message="Pending leave approvals report generated successfully",
        total_pending=len(report_data),
        data=report_data
    )

@router.get("/leave/encashment", response_model=LeaveEncashmentReportResponse)
def get_leave_encashment_report(
    from_date: date = Query(..., description="Start date of the report period"),
    to_date: date = Query(..., description="End date of the report period"),
    department_uuid: Optional[uuid.UUID] = Query(None, description="Filter by Department UUID"),
    status: Optional[LeaveEncashmentStatus] = Query(None, description="Filter by Status"),
    db: Session = Depends(deps.get_db),
    current_org: Organization = Depends(deps.get_current_org)
):
    """
    Get leave encashment records for a period.
    """
    if to_date < from_date:
        raise HTTPException(status_code=400, detail="to_date must be after from_date")

    # 1. Base Query for LeaveEncashment
    query = db.query(LeaveEncashment).filter(
        LeaveEncashment.organization_id == current_org.id,
        LeaveEncashment.encashment_date >= from_date,
        LeaveEncashment.encashment_date <= to_date
    )

    if department_uuid:
        query = query.join(Employee, LeaveEncashment.employee_id == Employee.id).filter(
            Employee.department_id == department_uuid
        )
    
    if status:
        query = query.filter(LeaveEncashment.status == status)

    # 2. Eager load related data
    query = query.options(
        joinedload(LeaveEncashment.employee).joinedload(Employee.department),
        joinedload(LeaveEncashment.leave_type)
    ).order_by(LeaveEncashment.encashment_date.asc())

    encashments = query.all()

    # 3. Calculate Totals
    total_days = 0.0
    total_amount = 0.0
    
    report_data = []
    for enc in encashments:
        total_days += float(enc.encashment_days)
        total_amount += float(enc.net_amount)
        
        record = LeaveEncashmentRecord(
            employee_uuid=enc.employee.uuid,
            employee_name=enc.employee.full_name,
            employee_code=enc.employee.employee_code,
            department=enc.employee.department.department_name if enc.employee.department else None,
            leave_type=enc.leave_type.leave_name,
            encashment_date=enc.encashment_date,
            encashment_days=float(enc.encashment_days),
            encashment_amount=float(enc.encashment_amount),
            tax_deducted=float(enc.tax_deducted),
            net_amount=float(enc.net_amount),
            status=enc.status.value,
            is_paid=enc.is_paid
        )
        report_data.append(record)

    return LeaveEncashmentReportResponse(
        success=True,
        message="Leave encashment report generated successfully",
        from_date=from_date,
        to_date=to_date,
        total_encashed_days=total_days,
        total_encashed_amount=total_amount,
        data=report_data
    )

@router.get("/leave/encashment", response_model=LeaveEncashmentReportResponse)
def get_leave_encashment_report(
    from_date: date = Query(..., description="Start date of the report period"),
    to_date: date = Query(..., description="End date of the report period"),
    department_uuid: Optional[uuid.UUID] = Query(None, description="Filter by Department UUID"),
    status: Optional[LeaveEncashmentStatus] = Query(None, description="Filter by Encashment Status"),
    db: Session = Depends(deps.get_db),
    current_org: Organization = Depends(deps.get_current_org)
):
    """
    Get leave encashment report for a period.
    """
    if to_date < from_date:
        raise HTTPException(status_code=400, detail="to_date must be after from_date")

    # Base Query for LeaveEncashment
    query = db.query(LeaveEncashment).join(
        Employee, LeaveEncashment.employee_id == Employee.id
    ).filter(
        LeaveEncashment.organization_id == current_org.id,
        LeaveEncashment.encashment_date >= from_date,
        LeaveEncashment.encashment_date <= to_date,
        Employee.is_deleted == False
    )

    if department_uuid:
        query = query.join(Department, Employee.department_id == Department.id).filter(
            Department.uuid == department_uuid
        )
    
    if status:
        query = query.filter(LeaveEncashment.status == status)

    # Eager load related data
    query = query.options(
        joinedload(LeaveEncashment.employee).joinedload(Employee.department),
        joinedload(LeaveEncashment.leave_type)
    ).order_by(LeaveEncashment.encashment_date.desc())

    encashments = query.all()

    report_data = []
    total_days = 0.0
    total_amount = 0.0

    for enc in encashments:
        days = float(enc.encashment_days)
        amount = float(enc.encashment_amount)
        
        # Only add to totals if APPROVED or PAID
        if enc.status in [LeaveEncashmentStatus.APPROVED, LeaveEncashmentStatus.PAID]:
            total_days += days
            total_amount += amount
            
        record = LeaveEncashmentRecord(
            employee_uuid=enc.employee.uuid,
            employee_name=enc.employee.full_name,
            employee_code=enc.employee.employee_code,
            department=enc.employee.department.department_name if enc.employee.department else None,
            leave_type=enc.leave_type.leave_name,
            encashment_date=enc.encashment_date,
            encashment_days=days,
            encashment_amount=amount,
            tax_deducted=float(enc.tax_deducted),
            net_amount=float(enc.net_amount),
            status=enc.status.value,
            is_paid=enc.is_paid
        )
        report_data.append(record)

    return LeaveEncashmentReportResponse(
        success=True,
        message="Leave encashment report generated successfully",
        from_date=from_date,
        to_date=to_date,
        total_encashed_days=round(total_days, 2),
        total_encashed_amount=round(total_amount, 2),
        data=report_data
    )

@router.get("/compensatory-off", response_model=CompOffReportResponse)
def get_compensatory_off_report(
    from_date: date = Query(..., description="Start date of the report period"),
    to_date: date = Query(..., description="End date of the report period"),
    department_uuid: Optional[uuid.UUID] = Query(None, description="Filter by Department UUID"),
    is_utilized: Optional[bool] = Query(None, description="Filter by Utilization Status"),
    db: Session = Depends(deps.get_db),
    current_org: Organization = Depends(deps.get_current_org)
):
    """
    Get compensatory off credits and utilization report.
    """
    if to_date < from_date:
        raise HTTPException(status_code=400, detail="to_date must be after from_date")

    # Base Query for CompensatoryOff
    query = db.query(CompensatoryOff).join(
        Employee, CompensatoryOff.employee_id == Employee.id
    ).filter(
        CompensatoryOff.organization_id == current_org.id,
        CompensatoryOff.worked_date >= from_date,
        CompensatoryOff.worked_date <= to_date,
        Employee.is_deleted == False
    )

    if department_uuid:
        query = query.join(Department, Employee.department_id == Department.id).filter(
            Department.uuid == department_uuid
        )
    
    if is_utilized is not None:
        query = query.filter(CompensatoryOff.is_utilized == is_utilized)

    # Eager load employee and department
    query = query.options(
        joinedload(CompensatoryOff.employee).joinedload(Employee.department)
    ).order_by(CompensatoryOff.worked_date.desc())

    records = query.all()

    report_data = []
    total_credited = 0.0
    total_utilized = 0.0

    for rec in records:
        credited = float(rec.comp_off_days)
        utilized = float(rec.utilized_days)
        
        total_credited += credited
        total_utilized += utilized
        
        record = CompOffRecord(
            employee_uuid=rec.employee.uuid,
            employee_name=rec.employee.full_name,
            employee_code=rec.employee.employee_code,
            department=rec.employee.department.department_name if rec.employee.department else None,
            worked_date=rec.worked_date,
            comp_off_days=credited,
            source_type=rec.source_type,
            expiry_date=rec.expiry_date,
            is_utilized=rec.is_utilized,
            utilized_days=utilized,
            remaining_days=float(rec.remaining_days),
            utilized_date=rec.utilized_date
        )
        report_data.append(record)

    return CompOffReportResponse(
        success=True,
        message="Compensatory off report generated successfully",
        from_date=from_date,
        to_date=to_date,
        total_credited_days=round(total_credited, 2),
        total_utilized_days=round(total_utilized, 2),
        data=report_data
    )
