# =============================================================================
# HRMS Permission Code Registry
# Each class maps a business module to its RBAC permission codes.
# These codes MUST match the permission_code column in the permissions table.
#
# Format: Codes are sequential integers stored as strings.
# Organization users always bypass all permission checks (super-user).
# =============================================================================


# ---------------------------------------------------------------------------
# EMPLOYEES MODULE  (1–4)
# ---------------------------------------------------------------------------
class EmployeePermissions:
    READ   = "1"
    CREATE = "2"
    UPDATE = "3"
    DELETE = "4"


# ---------------------------------------------------------------------------
# DEPARTMENTS MODULE  (5–8)
# ---------------------------------------------------------------------------
class DepartmentPermissions:
    READ   = "5"
    CREATE = "6"
    UPDATE = "7"
    DELETE = "8"


# ---------------------------------------------------------------------------
# LOCATIONS MODULE  (9–12)
# ---------------------------------------------------------------------------
class LocationPermissions:
    READ   = "9"
    CREATE = "10"
    UPDATE = "11"
    DELETE = "12"


# ---------------------------------------------------------------------------
# JOB TITLES MODULE  (13–16)
# ---------------------------------------------------------------------------
class JobTitlePermissions:
    READ   = "13"
    CREATE = "14"
    UPDATE = "15"
    DELETE = "16"


# ---------------------------------------------------------------------------
# COST CENTERS MODULE  (17–20)
# ---------------------------------------------------------------------------
class CostCenterPermissions:
    READ   = "17"
    CREATE = "18"
    UPDATE = "19"
    DELETE = "20"


# ---------------------------------------------------------------------------
# SHIFT MASTER MODULE  (21–24)
# ---------------------------------------------------------------------------
class ShiftPermissions:
    READ   = "21"
    CREATE = "22"
    UPDATE = "23"
    DELETE = "24"


# ---------------------------------------------------------------------------
# SHIFT ROSTER MODULE  (25–28)
# ---------------------------------------------------------------------------
class ShiftRosterPermissions:
    READ   = "25"
    CREATE = "26"
    UPDATE = "27"
    DELETE = "28"


# ---------------------------------------------------------------------------
# SHIFT ASSIGNMENTS MODULE  (29–32)
# ---------------------------------------------------------------------------
class ShiftAssignmentPermissions:
    READ   = "29"
    CREATE = "30"
    UPDATE = "31"
    DELETE = "32"


# ---------------------------------------------------------------------------
# ATTENDANCE MODULE  (33–35)
# ---------------------------------------------------------------------------
class AttendancePermissions:
    READ   = "33"
    UPDATE = "34"
    DELETE = "35"


# ---------------------------------------------------------------------------
# BIOMETRIC DEVICES MODULE  (36–38)
# ---------------------------------------------------------------------------
class BiometricDevicePermissions:
    READ   = "36"
    CREATE = "37"
    UPDATE = "38"


# ---------------------------------------------------------------------------
# ATTENDANCE REGULARIZATION MODULE  (39–42)
# ---------------------------------------------------------------------------
class AttendanceRegularizationPermissions:
    CREATE          = "39"   # Create regularization for others
    APPROVE_REJECT  = "40"   # Approve or reject a regularization
    READ_ALL        = "41"   # View all employees' regularizations
    DELETE          = "42"   # Cancel / delete a regularization


# ---------------------------------------------------------------------------
# OVERTIME MODULE  (43–45)
# ---------------------------------------------------------------------------
class OvertimePermissions:
    READ    = "43"
    CREATE  = "44"
    APPROVE = "45"


# ---------------------------------------------------------------------------
# LEAVE TYPES MODULE  (47–50)
# ---------------------------------------------------------------------------
class LeaveTypePermissions:
    READ   = "47"
    CREATE = "48"
    UPDATE = "49"
    DELETE = "50"


# ---------------------------------------------------------------------------
# LEAVE POLICY MODULE  (47–50)  — shares codes with LeaveType by design
# ---------------------------------------------------------------------------
class LeavePolicyPermissions:
    READ   = "47"
    CREATE = "48"
    UPDATE = "49"
    DELETE = "50"


# ---------------------------------------------------------------------------
# LEAVE BALANCE MODULE  (51, 53)
# ---------------------------------------------------------------------------
class LeaveBalancePermissions:
    READ   = "51"
    UPDATE = "53"


# ---------------------------------------------------------------------------
# COMPENSATORY OFF MODULE  (51–52)
# ---------------------------------------------------------------------------
class CompensatoryOffPermissions:
    READ   = "51"
    CREATE = "52"


# ---------------------------------------------------------------------------
# LEAVE ENCASHMENT MODULE  (51–54)
# ---------------------------------------------------------------------------
class LeaveEncashmentPermissions:
    READ   = "51"
    CREATE = "52"
    UPDATE = "53"
    DELETE = "54"


# ---------------------------------------------------------------------------
# LEAVE APPLICATIONS MODULE  (55–58)
# ---------------------------------------------------------------------------
class LeaveApplicationPermissions:
    READ   = "55"
    CREATE = "56"
    UPDATE = "57"
    DELETE = "58"


# ---------------------------------------------------------------------------
# HOLIDAYS MODULE  (59–62)
# ---------------------------------------------------------------------------
class HolidayPermissions:
    READ   = "59"
    CREATE = "60"
    UPDATE = "61"
    DELETE = "62"


# ---------------------------------------------------------------------------
# ATTENDANCE POLICY MODULE  (63–66)
# ---------------------------------------------------------------------------
class AttendancePolicyPermissions:
    READ   = "63"
    CREATE = "64"
    UPDATE = "65"
    DELETE = "66"


# ---------------------------------------------------------------------------
# GEOFENCE MODULE  (67–70)
# ---------------------------------------------------------------------------
class GeofencePermissions:
    READ   = "67"
    CREATE = "68"
    UPDATE = "69"
    DELETE = "70"


# ---------------------------------------------------------------------------
# ROLES & RBAC MODULE  (71–74)
# ---------------------------------------------------------------------------
class RolePermissions:
    READ   = "71"   # GET /roles, GET /roles/{uuid}, GET /roles/{uuid}/permissions
    CREATE = "72"   # POST /roles
    UPDATE = "73"   # PUT /roles/{uuid}, PUT /roles/{uuid}/permissions
    DELETE = "74"   # DELETE /roles/{uuid}


# ---------------------------------------------------------------------------
# INDUSTRIES MODULE  (75–78)
# ---------------------------------------------------------------------------
class IndustryPermissions:
    READ   = "75"
    CREATE = "76"
    UPDATE = "77"
    DELETE = "78"


# ---------------------------------------------------------------------------
# CLIENT MASTER MODULE  (79–82)
# ---------------------------------------------------------------------------
class ClientPermissions:
    READ   = "79"
    CREATE = "80"
    UPDATE = "81"
    DELETE = "82"


# ---------------------------------------------------------------------------
# PROJECT MASTER MODULE  (83–86)
# ---------------------------------------------------------------------------
class ProjectPermissions:
    READ   = "83"
    CREATE = "84"
    UPDATE = "85"
    DELETE = "86"


# ---------------------------------------------------------------------------
# TASK MASTER MODULE  (87–90)
# ---------------------------------------------------------------------------
class TaskPermissions:
    READ   = "87"
    CREATE = "88"
    UPDATE = "89"
    DELETE = "90"


# ---------------------------------------------------------------------------
# PROJECT MEMBERS MODULE  (91)
# ---------------------------------------------------------------------------
class ProjectMemberPermissions:
    MANAGE = "91"   # Add / update / remove members


# ---------------------------------------------------------------------------
# ACTIVITY TYPE MODULE  (92)
# ---------------------------------------------------------------------------
class ActivityTypePermissions:
    MANAGE = "92"   # Create / update / delete activity types


# ---------------------------------------------------------------------------
# TIMESHEET POLICY MODULE  (93)
# ---------------------------------------------------------------------------
class TimesheetPolicyPermissions:
    MANAGE = "93"   # Create / update / delete timesheet policies


# ---------------------------------------------------------------------------
# PAYROLL MODULE  (101–140)
# ---------------------------------------------------------------------------

class PayrollSalaryComponentPermissions:
    READ   = "101"
    CREATE = "102"
    UPDATE = "103"
    DELETE = "104"


class PayrollEmployeeSalaryPermissions:
    READ   = "105"
    CREATE = "106"
    UPDATE = "107"
    DELETE = "108"


class PayrollPeriodPermissions:
    READ    = "109"
    CREATE  = "110"
    UPDATE  = "111"
    PROCESS = "112"


class PayrollPayslipPermissions:
    READ    = "113"
    PUBLISH = "114"
    REVERSE = "115"


class PayrollLoanPermissions:
    READ   = "116"
    CREATE = "117"
    APPROVE= "118"


class PayrollReimbursementPermissions:
    READ   = "119"
    CREATE = "120"
    APPROVE= "121"


class PayrollTaxDeclarationPermissions:
    READ   = "122"
    CREATE = "123"
    APPROVE= "124"


class PayrollBankFilePermissions:
    READ   = "125"
    CREATE = "126"
    UPDATE = "145"


class PayrollAuditLogPermissions:
    READ   = "127"


class PayrollFinalSettlementPermissions:
    READ   = "128"
    CREATE = "129"
    APPROVE= "130"


class PayrollArrearPermissions:
    READ   = "131"
    CREATE = "132"
    APPROVE= "133"


class PayrollReportPermissions:
    READ   = "134"


class PayrollStatutoryFormPermissions:
    READ   = "135"
    CREATE = "136"


class PayrollReconciliationPermissions:
    READ   = "137"
    CREATE = "138"
    UPDATE = "138"


class PayrollJournalEntryPermissions:
    READ   = "139"
    CREATE = "140"
# ---------------------------------------------------------------------------
# BANK ACCOUNTS MODULE (141–144)
# ---------------------------------------------------------------------------
class PayrollBankAccountsPermissions:
    READ   = "141"
    CREATE = "142"
    UPDATE = "143"
    DELETE = "144"
