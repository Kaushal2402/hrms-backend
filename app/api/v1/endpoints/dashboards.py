import uuid
from typing import List, Optional, Union
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import func, or_, and_
from datetime import datetime, date, timedelta

from app.api import deps
from app.models.employee import (
    Employee, Department, EmploymentStatus, EmployeeDocument, 
    EmployeeCertification
)
from app.models.organization import Organization
from app.models.attendance import (
    AttendanceRecord, AttendanceLog, AttendanceStatus, CheckType,
    ShiftMaster, ShiftRoster, LeaveApplication, LeaveStatus,
    AttendanceRegularization, RegularizationStatus, OvertimeRequest,
    OvertimeStatus, Holiday, CompensatoryOff, CompensationType,
    LeaveBalance, WorkFromHomeRequest, OnDutyRequest, LeaveEncashment,
    LeaveEncashmentStatus, LeaveType
)
from app.schemas.dashboard import (
    EmployeeDashboardResponse, EmployeeDashboardData, EmployeeAttendanceStatus,
    UpcomingHoliday, OrganizationDashboardResponse, OrganizationDashboardData,
    OrganizationSnapshot, ApprovalCounts
)
from app.schemas.analytics import AttendanceKPIs, LeaveKPIs, AttendanceMetricData

router = APIRouter()

def get_manager_chain(db: Session, employee: Employee) -> List[dict]:
    chain = []
    current = employee.reporting_manager
    level = 1
    while current and level <= 5: # Limit to 5 levels to prevent infinite loops or excessive data
        chain.append({
            "name": current.full_name,
            "job_title": current.job_title.title_name if current.job_title else None,
            "photograph_url": current.photograph_url,
            "level": level
        })
        current = current.reporting_manager
        level += 1
    return chain

@router.get("/employee", response_model=EmployeeDashboardResponse)
def get_employee_dashboard(
    db: Session = Depends(deps.get_db),
    current_user: Union[Organization, Employee] = Depends(deps.get_current_user)
):
    """
    Get aggregated data for the employee dashboard.
    """
    # Resolve employee
    if isinstance(current_user, Organization):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Dashboard is only for employees. Organization should use /organization endpoint."
        )
    
    today = date.today()
    now = datetime.utcnow()
    
    # 1. Attendance Status
    # Get last punch
    last_punch = db.query(AttendanceLog).filter(
        AttendanceLog.employee_id == current_user.id
    ).order_by(AttendanceLog.punch_time.desc()).first()
    
    is_checked_in = False
    is_on_break = False
    if last_punch:
        if last_punch.check_type == CheckType.CHECK_IN:
            is_checked_in = True
        elif last_punch.check_type == CheckType.BREAK_START:
            is_checked_in = True
            is_on_break = True
        elif last_punch.check_type == CheckType.BREAK_END:
            is_checked_in = True
            
    # Get today's record
    attendance_record = db.query(AttendanceRecord).filter(
        AttendanceRecord.employee_id == current_user.id,
        AttendanceRecord.attendance_date == today
    ).first()
    
    # Night shift lookback if no today record and checked in
    if not attendance_record and is_checked_in and last_punch:
        attendance_record = db.query(AttendanceRecord).filter(
            AttendanceRecord.employee_id == current_user.id,
            AttendanceRecord.attendance_date == last_punch.punch_date
        ).first()

    total_work = float(attendance_record.total_work_hours or 0) if attendance_record else 0.0
    net_work = float(attendance_record.net_work_hours or 0) if attendance_record else 0.0
    total_break = float(attendance_record.break_hours or 0) if attendance_record else 0.0
    first_in = attendance_record.first_check_in if attendance_record else None

    # Real-time adjustment if currently checked in
    if is_checked_in and first_in:
        elapsed = (now - first_in).total_seconds() / 3600
        total_work = round(max(total_work, elapsed), 2)
        if is_on_break and last_punch:
            break_elapsed = (now - last_punch.punch_time).total_seconds() / 3600
            total_break = round(total_break + break_elapsed, 2)
        net_work = round(total_work - total_break, 2)

    attendance_status = EmployeeAttendanceStatus(
        is_checked_in=is_checked_in,
        is_on_break=is_on_break,
        last_punch_type=last_punch.check_type if last_punch else None,
        last_punch_time=last_punch.punch_time if last_punch else None,
        total_work_hours=total_work,
        net_work_hours=net_work,
        total_break_hours=total_break,
        is_late=attendance_record.is_late if attendance_record else False,
        late_minutes=attendance_record.late_by_minutes if attendance_record else 0,
        is_early_departure=attendance_record.is_early_departure if attendance_record else False,
        early_departure_minutes=attendance_record.early_departure_minutes if attendance_record else 0,
        is_late_departure=attendance_record.is_late_departure if attendance_record else False,
        late_departure_minutes=attendance_record.late_departure_minutes if attendance_record else 0
    )

    # 2. Leave Balances
    balances = db.query(LeaveBalance).filter(
        LeaveBalance.employee_id == current_user.id
    ).options(joinedload(LeaveBalance.leave_type)).all()

    # 3. Current Shift
    # Priority: Roster -> Default
    roster = db.query(ShiftRoster).filter(
        ShiftRoster.employee_id == current_user.id,
        ShiftRoster.roster_date == today,
        ShiftRoster.is_published == True
    ).options(joinedload(ShiftRoster.shift)).first()
    
    current_shift = roster.shift if roster else None
    if not current_shift:
        current_shift = db.query(ShiftMaster).filter(
            ShiftMaster.organization_id == current_user.organization_id,
            ShiftMaster.is_default == True,
            ShiftMaster.is_active == True
        ).first()

    # 4. Upcoming Holidays
    holidays = db.query(Holiday).filter(
        Holiday.organization_id == current_user.organization_id,
        Holiday.holiday_date >= today,
        Holiday.is_active == True
    ).order_by(Holiday.holiday_date.asc()).limit(3).all()
    
    upcoming_holidays = [
        UpcomingHoliday(
            holiday_name=h.holiday_name,
            holiday_date=h.holiday_date,
            day_name=h.holiday_date.strftime('%A'),
            is_optional=h.is_optional
        ) for h in holidays
    ]

    # 5. Recent Punches
    recent_punches = db.query(AttendanceLog).filter(
        AttendanceLog.employee_id == current_user.id
    ).order_by(AttendanceLog.punch_time.desc()).limit(5).all()

    # 6. Upcoming Leaves (Next 30 days)
    upcoming_leaves = db.query(LeaveApplication).filter(
        LeaveApplication.employee_id == current_user.id,
        LeaveApplication.from_date <= today + timedelta(days=30),
        LeaveApplication.to_date >= today
    ).options(joinedload(LeaveApplication.leave_type)).all()

    # 7. Weekly Roster (Next 7 days)
    roster_7days = db.query(ShiftRoster).filter(
        ShiftRoster.employee_id == current_user.id,
        ShiftRoster.roster_date >= today,
        ShiftRoster.roster_date < today + timedelta(days=7),
        ShiftRoster.is_published == True
    ).options(joinedload(ShiftRoster.shift)).order_by(ShiftRoster.roster_date.asc()).all()

    # 8. Manager Chain
    manager_chain = get_manager_chain(db, current_user)

    # 9. Recent Requests (Combined top 10)
    recent_reqs = []
    
    # Overtime
    ot_reqs = db.query(OvertimeRequest).filter(OvertimeRequest.employee_id == current_user.id).order_by(OvertimeRequest.created_at.desc()).limit(10).all()
    for r in ot_reqs:
        recent_reqs.append({
            "request_type": "Overtime",
            "request_date": r.attendance_date,
            "status": r.status,
            "details": f"{r.overtime_hours} hours",
            "created_at": r.created_at
        })
        
    # Regularization
    reg_reqs = db.query(AttendanceRegularization).filter(AttendanceRegularization.employee_id == current_user.id).order_by(AttendanceRegularization.created_at.desc()).limit(10).all()
    for r in reg_reqs:
        recent_reqs.append({
            "request_type": "Regularization",
            "request_date": r.attendance_date,
            "status": r.status,
            "details": f"{r.reason}",
            "created_at": r.created_at
        })
        
    # Encashment
    enc_reqs = db.query(LeaveEncashment).filter(LeaveEncashment.employee_id == current_user.id).order_by(LeaveEncashment.created_at.desc()).limit(10).all()
    for r in enc_reqs:
        recent_reqs.append({
            "request_type": "Encashment",
            "request_date": r.created_at.date(),
            "status": r.status,
            "details": f"{r.encashment_days} days",
            "created_at": r.created_at
        })

    # Sort and limit to 10
    recent_reqs.sort(key=lambda x: x["created_at"], reverse=True)
    recent_reqs = recent_reqs[:10]

    # 10. Expiring Items (Next 30 days)
    expiring_items = []
    
    docs = db.query(EmployeeDocument).filter(
        EmployeeDocument.employee_id == current_user.id,
        EmployeeDocument.expiry_date >= today,
        EmployeeDocument.expiry_date <= today + timedelta(days=30)
    ).all()
    for d in docs:
        expiring_items.append({
            "item_name": d.document_name,
            "item_type": "Document",
            "expiry_date": d.expiry_date,
            "days_remaining": (d.expiry_date - today).days
        })
        
    certs = db.query(EmployeeCertification).filter(
        EmployeeCertification.employee_id == current_user.id,
        EmployeeCertification.expiry_date >= today,
        EmployeeCertification.expiry_date <= today + timedelta(days=30)
    ).all()
    for c in certs:
        expiring_items.append({
            "item_name": c.certification_name,
            "item_type": "Certification",
            "expiry_date": c.expiry_date,
            "days_remaining": (c.expiry_date - today).days
        })

    dashboard_data = EmployeeDashboardData(
        attendance=attendance_status,
        leave_balances=[
            {
                "leave_type_name": b.leave_type.leave_name,
                "available_balance": float(b.available_balance),
                "total_balance": float(b.total_balance)
            } for b in balances
        ],
        current_shift={
            "shift_name": current_shift.shift_name,
            "start_time": current_shift.start_time,
            "end_time": current_shift.end_time,
            "shift_type": current_shift.shift_type
        } if current_shift else None,
        upcoming_holidays=[
            {
                "holiday_name": h.holiday_name,
                "holiday_date": h.holiday_date,
                "day_name": h.holiday_date.strftime('%A')
            } for h in holidays
        ],
        recent_punches=[
            {
                "punch_time": p.punch_time,
                "check_type": p.check_type,
                "location": p.location
            } for p in recent_punches
        ],
        upcoming_leaves=[
            {
                "leave_type_name": l.leave_type.leave_name,
                "from_date": l.from_date,
                "to_date": l.to_date,
                "status": l.status,
                "total_days": float(l.total_days)
            } for l in upcoming_leaves
        ],
        weekly_roster=[
            {
                "roster_date": r.roster_date,
                "shift_name": r.shift.shift_name if r.shift else None,
                "start_time": r.shift.start_time if r.shift else None,
                "end_time": r.shift.end_time if r.shift else None,
                "is_week_off": r.is_week_off
            } for r in roster_7days
        ],
        manager_chain=manager_chain,
        recent_requests=recent_reqs,
        expiring_items=expiring_items
    )

    return EmployeeDashboardResponse(
        success=True,
        message="Employee dashboard data retrieved successfully",
        data=dashboard_data
    )

@router.get("/organization", response_model=OrganizationDashboardResponse)
def get_organization_dashboard(
    db: Session = Depends(deps.get_db),
    current_org: Organization = Depends(deps.get_current_org)
):
    """
    Get aggregated data for the organization dashboard.
    """
    today = date.today()
    month_start = today.replace(day=1)
    
    # 1. Snapshot
    total_employees = db.query(Employee).filter(
        Employee.organization_id == current_org.id,
        Employee.is_deleted == False,
        Employee.employment_status == EmploymentStatus.ACTIVE
    ).count()
    
    attendance_today = db.query(AttendanceRecord).filter(
        AttendanceRecord.organization_id == current_org.id,
        AttendanceRecord.attendance_date == today
    ).all()
    
    present_today = sum(1 for r in attendance_today if r.status == AttendanceStatus.PRESENT)
    absent_today = total_employees - present_today # Simplified
    late_today = sum(1 for r in attendance_today if r.is_late)
    
    on_leave_today = db.query(LeaveApplication).filter(
        LeaveApplication.organization_id == current_org.id,
        LeaveApplication.status == LeaveStatus.APPROVED,
        LeaveApplication.from_date <= today,
        LeaveApplication.to_date >= today
    ).count()

    snapshot = OrganizationSnapshot(
        total_employees=total_employees,
        present_today=present_today,
        absent_today=max(0, absent_today - on_leave_today),
        on_leave_today=on_leave_today,
        late_today=late_today
    )

    # 2. Approval Counts
    pending_leaves = db.query(LeaveApplication).filter(
        LeaveApplication.organization_id == current_org.id,
        LeaveApplication.status == LeaveStatus.PENDING
    ).count()
    
    pending_regularizations = db.query(AttendanceRegularization).filter(
        AttendanceRegularization.organization_id == current_org.id,
        AttendanceRegularization.status == RegularizationStatus.PENDING
    ).count()
    
    pending_overtime = db.query(OvertimeRequest).filter(
        OvertimeRequest.organization_id == current_org.id,
        OvertimeRequest.status == OvertimeStatus.PENDING
    ).count()
    
    pending_wfh = db.query(WorkFromHomeRequest).filter(
        WorkFromHomeRequest.organization_id == current_org.id,
        WorkFromHomeRequest.status == 'pending'
    ).count()
    
    pending_on_duty = db.query(OnDutyRequest).filter(
        OnDutyRequest.organization_id == current_org.id,
        OnDutyRequest.status == 'pending'
    ).count()

    approvals = ApprovalCounts(
        pending_leaves=pending_leaves,
        pending_regularizations=pending_regularizations,
        pending_overtime=pending_overtime,
        pending_wfh=pending_wfh,
        pending_on_duty=pending_on_duty
    )

    # 3. KPIs (Current Month)
    records_month = db.query(AttendanceRecord).filter(
        AttendanceRecord.organization_id == current_org.id,
        AttendanceRecord.attendance_date >= month_start,
        AttendanceRecord.attendance_date <= today
    ).all()
    
    total_days = (today - month_start).days + 1
    potential_work_days = total_employees * total_days
    
    present_month = sum(1 for r in records_month if r.status == AttendanceStatus.PRESENT)
    absent_month = sum(1 for r in records_month if r.status == AttendanceStatus.ABSENT)
    late_month = sum(1 for r in records_month if r.is_late)
    early_month = sum(1 for r in records_month if r.is_early_departure)
    
    attendance_kpis = AttendanceKPIs(
        attendance_rate=round((present_month / potential_work_days * 100), 2) if potential_work_days > 0 else 0.0,
        absenteeism_rate=round((absent_month / potential_work_days * 100), 2) if potential_work_days > 0 else 0.0,
        late_arrival_rate=round((late_month / present_month * 100), 2) if present_month > 0 else 0.0,
        early_departure_rate=round((early_month / present_month * 100), 2) if present_month > 0 else 0.0,
        overtime_utilization=0.0
    )

    # 4. Leave KPIs
    leave_apps_month = db.query(LeaveApplication).filter(
        LeaveApplication.organization_id == current_org.id,
        LeaveApplication.from_date <= today,
        LeaveApplication.to_date >= month_start
    ).all()
    
    approved_month = [a for a in leave_apps_month if a.status == LeaveStatus.APPROVED]
    total_approved_days = sum(float(a.total_days) for a in approved_month)
    
    leave_kpis = LeaveKPIs(
        total_leave_days=total_approved_days,
        approval_rate=round((len(approved_month) / len(leave_apps_month) * 100), 2) if leave_apps_month else 0.0,
        rejection_rate=round((sum(1 for a in leave_apps_month if a.status == LeaveStatus.REJECTED) / len(leave_apps_month) * 100), 2) if leave_apps_month else 0.0,
        avg_leave_duration=round((total_approved_days / len(approved_month)), 2) if approved_month else 0.0,
        utilization_rate=0.0
    )

    # 5. Department-wise Attendance
    dept_stats = db.query(
        Department.department_name,
        func.count(AttendanceRecord.id)
    ).join(Employee, Department.id == Employee.department_id).join(
        AttendanceRecord, Employee.id == AttendanceRecord.employee_id
    ).filter(
        AttendanceRecord.organization_id == current_org.id,
        AttendanceRecord.attendance_date == today,
        AttendanceRecord.status == AttendanceStatus.PRESENT
    ).group_by(Department.department_name).all()
    
    department_metrics = [
        AttendanceMetricData(label=name, value=float(count)) for name, count in dept_stats
    ]

    dashboard_data = OrganizationDashboardData(
        snapshot=snapshot,
        approvals=approvals,
        attendance_kpis=attendance_kpis,
        leave_kpis=leave_kpis,
        department_wise_attendance=department_metrics
    )

    return OrganizationDashboardResponse(
        success=True,
        message="Organization dashboard data retrieved successfully",
        data=dashboard_data
    )
