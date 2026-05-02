# Import all the models, so that Base has them before being
# imported by Alembic
from app.db.base_class import Base  # noqa
from app.models.organization import Organization, Industry  # noqa
from app.models.employee import (
    Employee, Department, Location, JobTitle, CostCenter, 
    EmployeeDocument, EmployeeHistory, CustomFieldDefinition,
    EmployeeAlert, EmployeeAuditLog, EmployeeEducation, 
    EmployeeCertification, EmployeeWorkExperience,
    EmployeeAddress, EmployeePersonalInfo, EmployeeEmergencyContact
)  # noqa
from app.models.attendance import (
    ShiftMaster, LeaveBalance, LeaveApplication, Holiday,
    AttendanceRecord, AttendanceException, AttendanceRegularization,
    WorkFromHomeRequest, LeaveType, LeavePolicy, LeavePolicyMapping,
    BiometricDevice, EmployeeBiometricTemplate, ShiftAssignment,
    OvertimeRequest, Timesheet, TimesheetEntry,
    AttendanceNotification, AttendanceConfiguration
)  # noqa
from app.models.rbac import (
    RoleType, Role, Permission, RolePermission, UserRole
)  # noqa
from app.models.auth import TokenBlacklist  # noqa
from app.models.industry_templates import (
    IndustryDepartmentTemplate, IndustryJobTitleTemplate, IndustryRoleTemplate,
    IndustryShiftTemplate, IndustryAttendancePolicyTemplate, MasterCountryHoliday,
    IndustryLeaveTypeTemplate, IndustryLeavePolicyTemplate,
    QuickSetupJob
) # noqa

