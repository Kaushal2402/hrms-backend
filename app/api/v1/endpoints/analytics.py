from typing import List, Optional, Any
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import func
from datetime import date, timedelta
import uuid

from app.api import deps
from app.models.employee import Employee, Department, EmploymentStatus
from app.models.organization import Organization
from app.models.attendance import AttendanceRecord, AttendanceStatus, LeaveApplication, LeaveType, LeaveStatus, OvertimeRequest, OvertimeStatus
from app.schemas.analytics import (
    AttendanceMetricsResponse, AttendanceKPIs, AttendanceMetricData,
    LeaveMetricsResponse, LeaveKPIs,
    ProductivityMetricsResponse, ProductivityKPIs
)

router = APIRouter()

@router.get("/productivity", response_model=ProductivityMetricsResponse)
def get_productivity_metrics(
    from_date: date = Query(..., description="Start date of the analysis period"),
    to_date: date = Query(..., description="End date of the analysis period"),
    department_uuid: Optional[uuid.UUID] = Query(None, description="Filter by Department UUID"),
    db: Session = Depends(deps.get_db),
    current_org: Organization = Depends(deps.get_current_org)
):
    """
    Get productivity analytics including work hours and efficiency.
    """
    if to_date < from_date:
        raise HTTPException(status_code=400, detail="to_date must be after from_date")

    # 1. Base query for attendance records (Work Hours)
    query = db.query(AttendanceRecord).join(
        Employee, AttendanceRecord.employee_id == Employee.id
    ).filter(
        AttendanceRecord.organization_id == current_org.id,
        AttendanceRecord.attendance_date >= from_date,
        AttendanceRecord.attendance_date <= to_date,
        Employee.is_deleted == False
    )

    if department_uuid:
        query = query.join(Department, Employee.department_id == Department.id).filter(
            Department.uuid == department_uuid
        )

    records = query.all()
    
    # 2. Base query for overtime
    ot_query = db.query(OvertimeRequest).join(
        Employee, OvertimeRequest.employee_id == Employee.id
    ).filter(
        OvertimeRequest.organization_id == current_org.id,
        OvertimeRequest.attendance_date >= from_date,
        OvertimeRequest.attendance_date <= to_date,
        OvertimeRequest.status.in_([OvertimeStatus.APPROVED, OvertimeStatus.PAID]),
        Employee.is_deleted == False
    )
    if department_uuid:
        ot_query = ot_query.join(Department, Employee.department_id == Department.id).filter(
            Department.uuid == department_uuid
        )
    
    overtime_requests = ot_query.all()

    # 3. Get total active employees count in the period/department
    emp_query = db.query(Employee).filter(
        Employee.organization_id == current_org.id,
        Employee.is_deleted == False,
        Employee.employment_status == EmploymentStatus.ACTIVE
    )
    if department_uuid:
        emp_query = emp_query.join(Department).filter(Department.uuid == department_uuid)
    
    total_employees = emp_query.count()
    total_days = (to_date - from_date).days + 1
    # Standard 8-hour workday assumption
    expected_work_hours = total_employees * 8.0 * total_days 

    # 4. Calculate KPIs
    actual_work_hours = sum(float(r.net_work_hours) for r in records)
    total_ot_hours = sum(float(r.overtime_hours) for r in overtime_requests)
    
    avg_per_day = (actual_work_hours / total_days) if total_days > 0 else 0.0
    ot_ratio = (total_ot_hours / actual_work_hours * 100) if actual_work_hours > 0 else 0.0
    efficiency = (actual_work_hours / expected_work_hours * 100) if expected_work_hours > 0 else 0.0

    kpis = ProductivityKPIs(
        total_work_hours=round(actual_work_hours, 2),
        avg_work_hours_per_day=round(avg_per_day, 2),
        total_overtime_hours=round(total_ot_hours, 2),
        overtime_to_work_ratio=round(ot_ratio, 2),
        efficiency_score=round(efficiency, 2)
    )

    # 5. Detailed Metrics (Breakdown by Day)
    date_map = {}
    curr = from_date
    while curr <= to_date:
        date_map[curr] = {"work": 0.0, "ot": 0.0}
        curr += timedelta(days=1)
        
    for r in records:
        if r.attendance_date in date_map:
            date_map[r.attendance_date]["work"] += float(r.net_work_hours)
    
    for ot in overtime_requests:
        if ot.attendance_date in date_map:
            date_map[ot.attendance_date]["ot"] += float(ot.overtime_hours)

    detailed_metrics = [
        AttendanceMetricData(
            label="Daily Work Hours", 
            value=round(actual_work_hours, 2), 
            trend_data=[round(v["work"], 2) for k, v in sorted(date_map.items())]
        ),
        AttendanceMetricData(
            label="Daily Overtime Hours", 
            value=round(total_ot_hours, 2), 
            trend_data=[round(v["ot"], 2) for k, v in sorted(date_map.items())]
        )
    ]

    return ProductivityMetricsResponse(
        success=True,
        message="Productivity metrics retrieved successfully",
        from_date=from_date,
        to_date=to_date,
        kpis=kpis,
        detailed_metrics=detailed_metrics
    )

@router.get("/attendance-metrics", response_model=AttendanceMetricsResponse)
def get_attendance_metrics(
    from_date: date = Query(..., description="Start date of the analysis period"),
    to_date: date = Query(..., description="End date of the analysis period"),
    metric_type: str = Query("summary", description="Type of metrics: summary, trend, departmental"),
    department_uuid: Optional[uuid.UUID] = Query(None, description="Filter by Department UUID"),
    db: Session = Depends(deps.get_db),
    current_org: Organization = Depends(deps.get_current_org)
):
    """
    Get attendance KPIs and metrics for analytics.
    """
    if to_date < from_date:
        raise HTTPException(status_code=400, detail="to_date must be after from_date")

    # 1. Base query for attendance records
    query = db.query(AttendanceRecord).join(
        Employee, AttendanceRecord.employee_id == Employee.id
    ).filter(
        AttendanceRecord.organization_id == current_org.id,
        AttendanceRecord.attendance_date >= from_date,
        AttendanceRecord.attendance_date <= to_date,
        Employee.is_deleted == False
    )

    if department_uuid:
        query = query.join(Department, Employee.department_id == Department.id).filter(
            Department.uuid == department_uuid
        )

    records = query.all()
    
    # 2. Get total active employees count in the period/department
    emp_query = db.query(Employee).filter(
        Employee.organization_id == current_org.id,
        Employee.is_deleted == False,
        Employee.employment_status == EmploymentStatus.ACTIVE
    )
    if department_uuid:
        emp_query = emp_query.join(Department).filter(Department.uuid == department_uuid)
    
    total_employees = emp_query.count()
    total_days = (to_date - from_date).days + 1
    potential_work_days = total_employees * total_days # Simplistic, doesn't exclude weekends/holidays yet

    # 3. Calculate KPIs
    present_count = sum(1 for r in records if r.status == AttendanceStatus.PRESENT)
    absent_count = sum(1 for r in records if r.status == AttendanceStatus.ABSENT)
    late_count = sum(1 for r in records if r.is_late)
    early_count = sum(1 for r in records if r.is_early_departure)
    
    # Rates
    attendance_rate = (present_count / potential_work_days * 100) if potential_work_days > 0 else 0.0
    absenteeism_rate = (absent_count / potential_work_days * 100) if potential_work_days > 0 else 0.0
    late_rate = (late_count / present_count * 100) if present_count > 0 else 0.0
    early_rate = (early_count / present_count * 100) if present_count > 0 else 0.0

    kpis = AttendanceKPIs(
        attendance_rate=round(attendance_rate, 2),
        absenteeism_rate=round(absenteeism_rate, 2),
        late_arrival_rate=round(late_rate, 2),
        early_departure_rate=round(early_rate, 2),
        overtime_utilization=0.0 # Placeholder
    )

    # 4. Detailed Metrics based on metric_type
    detailed_metrics = []
    
    if metric_type == "summary":
        detailed_metrics = [
            AttendanceMetricData(label="Total Present Days", value=float(present_count)),
            AttendanceMetricData(label="Total Absent Days", value=float(absent_count)),
            AttendanceMetricData(label="Late In Instances", value=float(late_count)),
            AttendanceMetricData(label="Early Out Instances", value=float(early_count))
        ]
    elif metric_type == "trend":
        # Calculate daily trend for the period
        date_map = {}
        curr = from_date
        while curr <= to_date:
            date_map[curr] = 0
            curr += timedelta(days=1)
            
        for r in records:
            if r.status == AttendanceStatus.PRESENT:
                date_map[r.attendance_date] += 1
        
        detailed_metrics = [
            AttendanceMetricData(
                label="Daily Attendance Count", 
                value=float(present_count), 
                trend_data=[float(v) for k, v in sorted(date_map.items())]
            )
        ]

    return AttendanceMetricsResponse(
        success=True,
        message="Attendance metrics retrieved successfully",
        from_date=from_date,
        to_date=to_date,
        metric_type=metric_type,
        kpis=kpis,
        detailed_metrics=detailed_metrics
    )

@router.get("/leave-metrics", response_model=LeaveMetricsResponse)
def get_leave_metrics(
    from_date: date = Query(..., description="Start date of the analysis period"),
    to_date: date = Query(..., description="End date of the analysis period"),
    metric_type: str = Query("summary", description="Type of metrics: summary, trend, leave_type"),
    leave_type_uuid: Optional[uuid.UUID] = Query(None, description="Filter by Leave Type UUID"),
    db: Session = Depends(deps.get_db),
    current_org: Organization = Depends(deps.get_current_org)
):
    """
    Get leave KPIs and metrics for analytics.
    """
    if to_date < from_date:
        raise HTTPException(status_code=400, detail="to_date must be after from_date")

    # 1. Base query for leave applications
    query = db.query(LeaveApplication).filter(
        LeaveApplication.organization_id == current_org.id,
        LeaveApplication.from_date <= to_date,
        LeaveApplication.to_date >= from_date
    )

    if leave_type_uuid:
        query = query.join(LeaveType).filter(LeaveType.uuid == leave_type_uuid)

    apps = query.all()

    # 2. Calculate KPIs
    approved_apps = [a for a in apps if a.status == LeaveStatus.APPROVED]
    rejected_apps = [a for a in apps if a.status == LeaveStatus.REJECTED]
    total_apps_count = len(apps)
    
    total_approved_days = sum(float(a.total_days) for a in approved_apps)
    approval_rate = (len(approved_apps) / total_apps_count * 100) if total_apps_count > 0 else 0.0
    rejection_rate = (len(rejected_apps) / total_apps_count * 100) if total_apps_count > 0 else 0.0
    avg_duration = (total_approved_days / len(approved_apps)) if len(approved_apps) > 0 else 0.0

    kpis = LeaveKPIs(
        total_leave_days=round(total_approved_days, 2),
        approval_rate=round(approval_rate, 2),
        rejection_rate=round(rejection_rate, 2),
        avg_leave_duration=round(avg_duration, 2),
        utilization_rate=0.0 # Placeholder
    )

    # 3. Detailed Metrics based on metric_type
    detailed_metrics = []
    
    if metric_type == "summary":
        detailed_metrics = [
            AttendanceMetricData(label="Total Applications", value=float(total_apps_count)),
            AttendanceMetricData(label="Approved Applications", value=float(len(approved_apps))),
            AttendanceMetricData(label="Rejected Applications", value=float(len(rejected_apps))),
            AttendanceMetricData(label="Total Approved Leave Days", value=float(total_approved_days))
        ]
    elif metric_type == "trend":
        # Calculate daily trend (overlap logic)
        date_map = {}
        curr = from_date
        while curr <= to_date:
            date_map[curr] = 0.0
            curr += timedelta(days=1)
            
        for a in approved_apps:
            overlap_start = max(from_date, a.from_date)
            overlap_end = min(to_date, a.to_date)
            
            d = overlap_start
            while d <= overlap_end:
                if d in date_map:
                    # Simple 1 day per date overlap
                    date_map[d] += 1.0
                d += timedelta(days=1)
                
        detailed_metrics = [
            AttendanceMetricData(
                label="Daily Leave Count", 
                value=float(total_approved_days), 
                trend_data=[float(v) for k, v in sorted(date_map.items())]
            )
        ]
    elif metric_type == "leave_type":
        # Group by leave type
        type_map = {} # name -> count
        for a in approved_apps:
            lt_name = a.leave_type.leave_name
            type_map[lt_name] = type_map.get(lt_name, 0.0) + float(a.total_days)
            
        for name, value in type_map.items():
            detailed_metrics.append(AttendanceMetricData(label=name, value=value))

    return LeaveMetricsResponse(
        success=True,
        message="Leave metrics retrieved successfully",
        from_date=from_date,
        to_date=to_date,
        metric_type=metric_type,
        kpis=kpis,
        detailed_metrics=detailed_metrics
    )
