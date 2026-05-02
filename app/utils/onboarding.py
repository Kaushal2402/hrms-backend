from sqlalchemy.orm import Session
from app.models.organization import Organization
from app.models.employee import Department, JobTitle, Location
from app.models.attendance import AttendancePolicy, ShiftMaster, Holiday, LeavePolicy, LeaveType
from app.models.rbac import Role
from datetime import datetime

def get_onboarding_progress(db: Session, org_id: int):
    """
    Check the onboarding progress for an organization.
    Returns a dictionary with status of each step and overall percentage.
    """
    # 1. Organization Profile
    org = db.query(Organization).filter(Organization.id == org_id).first()
    # Profile is considered "in progress" but not completed if legal requirements (Logo, GST, PAN, Industry) are missing
    # However, name and email are mandatory at registration.
    is_profile_completed = all([org.logo, org.gst_number, org.pan_number, org.address_line1, org.industry])

    # 2. Departments
    is_departments_setup = db.query(Department).filter(
        Department.organization_id == org_id,
        Department.is_deleted == False
    ).count() > 0

    # 3. Job Titles
    is_job_titles_setup = db.query(JobTitle).filter(
        JobTitle.organization_id == org_id,
        JobTitle.is_deleted == False
    ).count() > 0

    # 4. Locations
    is_locations_setup = db.query(Location).filter(
        Location.organization_id == org_id,
        Location.is_deleted == False
    ).count() > 0

    # 5. Attendance Policy
    is_attendance_policy_setup = db.query(AttendancePolicy).filter(
        AttendancePolicy.organization_id == org_id,
        AttendancePolicy.is_deleted == False
    ).count() > 0

    # 6. Shift Type
    is_shift_types_setup = db.query(ShiftMaster).filter(
        ShiftMaster.organization_id == org_id,
        ShiftMaster.is_deleted == False
    ).count() > 0

    # 7. Holiday Setup
    current_year = datetime.utcnow().year
    is_holiday_setup = db.query(Holiday).filter(
        Holiday.organization_id == org_id,
        Holiday.holiday_year == current_year,
        Holiday.is_deleted == False
    ).count() > 0

    # 8. Leave Policy
    is_leave_policy_setup = db.query(LeavePolicy).filter(
        LeavePolicy.organization_id == org_id,
        LeavePolicy.is_deleted == False
    ).count() > 0

    # 9. Leave Type
    is_leave_types_setup = db.query(LeaveType).filter(
        LeaveType.organization_id == org_id,
        LeaveType.is_deleted == False
    ).count() > 0

    # 10. Roles and Permissions
    # We check for non-system roles (custom roles)
    is_roles_permissions_setup = db.query(Role).filter(
        Role.organization_id == org_id,
        Role.is_system_role == False,
        Role.is_deleted == False
    ).count() > 0

    steps = {
        "is_profile_completed": is_profile_completed,
        "is_departments_setup": is_departments_setup,
        "is_job_titles_setup": is_job_titles_setup,
        "is_locations_setup": is_locations_setup,
        "is_attendance_policy_setup": is_attendance_policy_setup,
        "is_shift_types_setup": is_shift_types_setup,
        "is_holiday_setup": is_holiday_setup,
        "is_leave_policy_setup": is_leave_policy_setup,
        "is_leave_types_setup": is_leave_types_setup,
        "is_roles_permissions_setup": is_roles_permissions_setup,
    }

    completed_count = sum(1 for status in steps.values() if status)
    total_steps = len(steps)
    overall_percentage = int((completed_count / total_steps) * 100)

    return {
        **steps,
        "total_steps": total_steps,
        "completed_steps": completed_count,
        "overall_percentage": overall_percentage
    }
