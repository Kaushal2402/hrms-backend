import uuid
from datetime import datetime
from typing import List, Optional, Any
from sqlalchemy.orm import Session
from app.models.organization import Organization
from app.models.industry_templates import (
    IndustryDepartmentTemplate, IndustryJobTitleTemplate, IndustryRoleTemplate,
    IndustryShiftTemplate, IndustryAttendancePolicyTemplate, MasterCountryHoliday,
    IndustryLeaveTypeTemplate, IndustryLeavePolicyTemplate,
    QuickSetupJob, QuickSetupStatus
)
from app.models.employee import Department, JobTitle, Location
from app.models.attendance import (
    ShiftMaster, AttendancePolicy, Holiday, 
    LeaveType, LeavePolicy, LeavePolicyMapping
)
from app.models.rbac import Role, RolePermission, Permission

def run_quick_setup_background(db: Session, job_id: int):
    """
    Background task to execute the quick setup with progress tracking.
    """
    job = db.query(QuickSetupJob).get(job_id)
    if not job:
        return

    org_id = job.organization_id
    org = db.query(Organization).get(org_id)
    job.status = QuickSetupStatus.PROCESSING
    job.progress_percentage = 0
    job.logs = []
    db.commit()

    steps = [
        ("Location", _setup_location, 'setup_location'),
        ("Holidays", _setup_holidays, 'setup_holidays'),
        ("Departments", _clone_departments, 'department_ids'),
        ("Job Titles", _clone_job_titles, 'job_title_ids'),
        ("Roles", _clone_roles, 'role_ids'),
        ("Shifts", _clone_shifts, 'shift_ids'),
        ("Attendance Policies", _clone_attendance_policies, 'attendance_policy_ids'),
        ("Leave Types", _clone_leave_types, 'leave_type_ids'),
        ("Leave Policies", _clone_leave_policies, 'leave_policy_ids'),
    ]

    total_steps = len(steps)
    
    try:
        selections = job.selections
        
        for i, (step_name, func, selection_key) in enumerate(steps):
            selection_val = selections.get(selection_key)
            
            should_run = False
            if isinstance(selection_val, list) and len(selection_val) > 0:
                should_run = True
            elif isinstance(selection_val, bool) and selection_val is True:
                should_run = True

            if should_run:
                try:
                    if selection_key == 'setup_location':
                        msg = func(db, org)
                    elif selection_key == 'setup_holidays':
                        msg = func(db, org, selections.get('selected_holidays', []))
                    else:
                        msg = func(db, org_id, selection_val)
                    
                    _add_log(job, step_name, "completed", msg)
                except Exception as e:
                    _add_log(job, step_name, "failed", str(e))
            else:
                _add_log(job, step_name, "skipped", "No selection made")

            job.progress_percentage = int(((i + 1) / total_steps) * 100)
            db.commit()

        job.status = QuickSetupStatus.COMPLETED
        job.completed_at = datetime.utcnow()
        job.progress_percentage = 100
        db.commit()

    except Exception as e:
        db.rollback()
        job.status = QuickSetupStatus.FAILED
        job.error_log = str(e)
        _add_log(job, "System", "failed", f"Critical Error: {str(e)}")
        db.commit()

def _add_log(job: QuickSetupJob, step: str, status: str, message: str):
    if job.logs is None:
        job.logs = []
    new_logs = list(job.logs)
    new_logs.append({
        "step": step,
        "status": status,
        "message": message,
        "timestamp": datetime.utcnow().isoformat()
    })
    job.logs = new_logs

def _setup_location(db: Session, org: Organization) -> str:
    existing = db.query(Location).filter(Location.organization_id == org.id).first()
    if not existing:
        new_loc = Location(
            organization_id=org.id,
            location_code="HQ",
            location_name="Headquarters",
            location_type="head_office",
            address_line1=org.address_line1,
            address_line2=org.address_line2,
            city=org.city,
            state=org.state,
            country=org.country or "India",
            pincode=org.pincode
        )
        db.add(new_loc)
        db.flush()
        return "Headquarters created successfully"
    return "Location already exists"

def _setup_holidays(db: Session, org: Organization, selected_holidays: List[dict]) -> str:
    current_year = datetime.utcnow().year
    count = 0
    for sh in selected_holidays:
        # Check if already exists
        exists = db.query(Holiday).filter(
            Holiday.organization_id == org.id,
            Holiday.holiday_name == sh["holiday_name"],
            Holiday.holiday_date == sh["holiday_date"]
        ).first()
        
        if not exists:
            # Defensive mapping to ensure Enum compatibility
            h_type_raw = sh.get("holiday_type", "public").lower()
            if "public" in h_type_raw:
                h_type = "public"
            elif "optional" in h_type_raw or "observance" in h_type_raw:
                h_type = "optional"
            elif "restricted" in h_type_raw:
                h_type = "restricted"
            else:
                h_type = "public"

            new_h = Holiday(
                organization_id=org.id,
                holiday_name=sh["holiday_name"],
                holiday_date=sh["holiday_date"],
                holiday_type=h_type,
                holiday_year=current_year
            )
            db.add(new_h)
            count += 1
    db.flush()
    return f"{count} selected holidays added to calendar"

def _clone_departments(db: Session, org_id: int, template_ids: List[int]) -> str:
    count = 0
    for tid in template_ids:
        tmpl = db.query(IndustryDepartmentTemplate).get(tid)
        if tmpl:
            exists = db.query(Department).filter(
                Department.organization_id == org_id,
                Department.department_code == tmpl.department_code
            ).first()
            if not exists:
                new_d = Department(
                    organization_id=org_id,
                    department_code=tmpl.department_code,
                    department_name=tmpl.department_name,
                    description=tmpl.description
                )
                db.add(new_d)
                count += 1
    db.flush()
    return f"{count} departments created"

def _clone_job_titles(db: Session, org_id: int, template_ids: List[int]) -> str:
    count = 0
    for tid in template_ids:
        tmpl = db.query(IndustryJobTitleTemplate).get(tid)
        if tmpl:
            exists = db.query(JobTitle).filter(
                JobTitle.organization_id == org_id,
                JobTitle.title_code == tmpl.title_code
            ).first()
            if not exists:
                new_j = JobTitle(
                    organization_id=org_id,
                    title_code=tmpl.title_code,
                    title_name=tmpl.title_name,
                    job_level=tmpl.job_level,
                    job_family=tmpl.job_family,
                    description=tmpl.description,
                    responsibilities=tmpl.responsibilities,
                    qualifications=tmpl.qualifications
                )
                db.add(new_j)
                count += 1
    db.flush()
    return f"{count} job titles created"

def _clone_roles(db: Session, org_id: int, template_ids: List[int]) -> str:
    count = 0
    for tid in template_ids:
        tmpl = db.query(IndustryRoleTemplate).get(tid)
        if tmpl:
            exists = db.query(Role).filter(
                Role.organization_id == org_id,
                Role.role_code == tmpl.role_code
            ).first()
            if not exists:
                new_r = Role(
                    organization_id=org_id,
                    role_code=tmpl.role_code,
                    role_name=tmpl.role_name,
                    role_description=tmpl.role_description,
                    role_level=tmpl.role_level,
                    scope=tmpl.scope,
                    color_code=tmpl.color_code,
                    icon=tmpl.icon,
                    is_default=True
                )
                db.add(new_r)
                db.flush()
                
                if tmpl.permission_codes:
                    perms = db.query(Permission).filter(
                        Permission.permission_code.in_(tmpl.permission_codes)
                    ).all()
                    for p in perms:
                        rp = RolePermission(role_id=new_r.id, permission_id=p.id)
                        db.add(rp)
                count += 1
    db.flush()
    return f"{count} default roles created with permissions"

def _clone_shifts(db: Session, org_id: int, template_ids: List[int]) -> str:
    count = 0
    for tid in template_ids:
        tmpl = db.query(IndustryShiftTemplate).get(tid)
        if tmpl:
            exists = db.query(ShiftMaster).filter(
                ShiftMaster.organization_id == org_id,
                ShiftMaster.shift_code == tmpl.shift_code
            ).first()
            if not exists:
                new_s = ShiftMaster(
                    organization_id=org_id,
                    shift_code=tmpl.shift_code,
                    shift_name=tmpl.shift_name,
                    shift_type=tmpl.shift_type,
                    start_time=tmpl.start_time,
                    end_time=tmpl.end_time,
                    work_hours=tmpl.work_hours,
                    break_hours=tmpl.break_hours,
                    has_break=tmpl.has_break,
                    late_arrival_grace_minutes=tmpl.late_arrival_grace_minutes,
                    early_departure_grace_minutes=tmpl.early_departure_grace_minutes,
                    week_off_days=tmpl.week_off_days
                )
                db.add(new_s)
                count += 1
    db.flush()
    return f"{count} shifts created"

def _clone_attendance_policies(db: Session, org_id: int, template_ids: List[int]) -> str:
    count = 0
    for tid in template_ids:
        tmpl = db.query(IndustryAttendancePolicyTemplate).get(tid)
        if tmpl:
            exists = db.query(AttendancePolicy).filter(
                AttendancePolicy.organization_id == org_id,
                AttendancePolicy.policy_name == tmpl.policy_name
            ).first()
            if not exists:
                new_p = AttendancePolicy(
                    organization_id=org_id,
                    policy_name=tmpl.policy_name,
                    working_days_per_week=tmpl.working_days_per_week,
                    working_hours_per_day=tmpl.working_hours_per_day,
                    late_arrival_grace=tmpl.late_arrival_grace,
                    early_departure_grace=tmpl.early_departure_grace,
                    overtime_enabled=tmpl.overtime_enabled,
                    regularization_allowed=tmpl.regularization_allowed,
                    effective_from=datetime.utcnow().date()
                )
                db.add(new_p)
                count += 1
    db.flush()
    return f"{count} attendance policies created"

def _clone_leave_types(db: Session, org_id: int, template_ids: List[int]) -> str:
    count = 0
    for tid in template_ids:
        tmpl = db.query(IndustryLeaveTypeTemplate).get(tid)
        if tmpl:
            exists = db.query(LeaveType).filter(
                LeaveType.organization_id == org_id,
                LeaveType.leave_code == tmpl.leave_code
            ).first()
            if not exists:
                new_lt = LeaveType(
                    organization_id=org_id,
                    leave_code=tmpl.leave_code,
                    leave_name=tmpl.leave_name,
                    description=tmpl.description,
                    accrual_type=tmpl.accrual_type,
                    accrual_rate=tmpl.accrual_rate,
                    max_balance=tmpl.max_balance,
                    color_code=tmpl.color_code
                )
                db.add(new_lt)
                count += 1
    db.flush()
    return f"{count} leave types created"

def _clone_leave_policies(db: Session, org_id: int, template_ids: List[int]) -> str:
    count = 0
    for tid in template_ids:
        tmpl = db.query(IndustryLeavePolicyTemplate).get(tid)
        if tmpl:
            exists = db.query(LeavePolicy).filter(
                LeavePolicy.organization_id == org_id,
                LeavePolicy.policy_name == tmpl.policy_name
            ).first()
            if not exists:
                new_lp = LeavePolicy(
                    organization_id=org_id,
                    policy_name=tmpl.policy_name,
                    description=tmpl.description,
                    effective_from=datetime.utcnow().date(),
                    is_default=True
                )
                db.add(new_lp)
                db.flush()
                
                if tmpl.leave_type_codes:
                    lts = db.query(LeaveType).filter(
                        LeaveType.organization_id == org_id,
                        LeaveType.leave_code.in_(tmpl.leave_type_codes)
                    ).all()
                    for lt in lts:
                        # Find the quota from the industry template
                        lt_tmpl = db.query(IndustryLeaveTypeTemplate).filter(
                            IndustryLeaveTypeTemplate.industry_id == tmpl.industry_id,
                            IndustryLeaveTypeTemplate.leave_code == lt.leave_code
                        ).first()
                        
                        quota = lt_tmpl.annual_quota if lt_tmpl else 0
                        
                        mapping = LeavePolicyMapping(
                            leave_policy_id=new_lp.id,
                            leave_type_id=lt.id,
                            annual_quota=quota
                        )
                        db.add(mapping)
                count += 1
    db.flush()
    return f"{count} default leave policies created"
