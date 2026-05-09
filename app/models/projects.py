from sqlalchemy import (
    Column, Integer, String, Boolean, DateTime, Text,
    Enum, Date, Numeric, ForeignKey, Index, JSON, UniqueConstraint
)
from sqlalchemy.orm import relationship
from datetime import datetime
import uuid
import enum

from app.db.base_class import Base
from app.models.organization import GUID


# ============================================================
# ENUMS
# ============================================================

class ProjectType(str, enum.Enum):
    BILLABLE = "billable"
    NON_BILLABLE = "non_billable"
    INTERNAL = "internal"
    RD = "rd"

class ProjectStatus(str, enum.Enum):
    PLANNING = "planning"
    ACTIVE = "active"
    ON_HOLD = "on_hold"
    COMPLETED = "completed"
    CANCELLED = "cancelled"

class ProjectPriority(str, enum.Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"

class BillingType(str, enum.Enum):
    FIXED = "fixed"
    HOURLY = "hourly"
    RETAINER = "retainer"

class TaskStatus(str, enum.Enum):
    BACKLOG = "backlog"
    TODO = "todo"
    IN_PROGRESS = "in_progress"
    REVIEW = "review"
    DONE = "done"
    CANCELLED = "cancelled"

class TaskType(str, enum.Enum):
    FEATURE = "feature"
    BUG = "bug"
    SUPPORT = "support"
    RESEARCH = "research"
    ADMIN = "admin"

class MemberRole(str, enum.Enum):
    MANAGER = "manager"
    DEVELOPER = "developer"
    REVIEWER = "reviewer"
    OBSERVER = "observer"

class TimesheetPeriodType(str, enum.Enum):
    WEEKLY = "weekly"
    BI_WEEKLY = "bi_weekly"
    MONTHLY = "monthly"

class PolicyApplicableTo(str, enum.Enum):
    ALL = "all"
    DEPARTMENT = "department"
    EMPLOYEE_TYPE = "employee_type"


# ============================================================
# MODULE 1: CLIENT MASTER
# ============================================================

class ProjectClient(Base):
    """Clients / billing entities for projects"""
    __tablename__ = "project_clients"

    id = Column(Integer, primary_key=True, index=True)
    uuid = Column(GUID(as_uuid=True), default=uuid.uuid4, unique=True, nullable=False, index=True)
    organization_id = Column(Integer, ForeignKey("organization.id"), nullable=False, index=True)

    # Identity
    client_code = Column(String(50), nullable=False, index=True)
    client_name = Column(String(200), nullable=False)

    # Contact
    contact_person = Column(String(150), nullable=True)
    contact_email = Column(String(150), nullable=True)
    contact_phone = Column(String(30), nullable=True)

    # Billing
    billing_currency = Column(String(10), default="INR", nullable=True)
    default_billing_rate = Column(Numeric(10, 2), nullable=True)
    address = Column(Text, nullable=True)

    # Flags
    is_active = Column(Boolean, default=True, index=True)
    is_internal = Column(Boolean, default=False)  # True = no external billing

    # Audit
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    created_by = Column(Integer, ForeignKey("employees.id"), nullable=True)
    is_deleted = Column(Boolean, default=False, nullable=False)
    deleted_at = Column(DateTime, nullable=True)

    # Relationships
    projects = relationship("Project", back_populates="client")

    __table_args__ = (
        UniqueConstraint("organization_id", "client_code", name="uq_client_org_code"),
        Index("idx_client_org_active", "organization_id", "is_active"),
    )


# ============================================================
# MODULE 2: PROJECT MASTER
# ============================================================

class Project(Base):
    """Project master — main work unit for timesheets"""
    __tablename__ = "projects"

    id = Column(Integer, primary_key=True, index=True)
    uuid = Column(GUID(as_uuid=True), default=uuid.uuid4, unique=True, nullable=False, index=True)
    organization_id = Column(Integer, ForeignKey("organization.id"), nullable=False, index=True)

    # Client (nullable for internal projects)
    client_id = Column(Integer, ForeignKey("project_clients.id"), nullable=True, index=True)

    # Identity
    project_code = Column(String(50), nullable=False, index=True)
    project_name = Column(String(200), nullable=False)
    description = Column(Text, nullable=True)

    # Classification
    project_type = Column(Enum(ProjectType), nullable=False, default=ProjectType.BILLABLE)
    status = Column(Enum(ProjectStatus), nullable=False, default=ProjectStatus.PLANNING, index=True)
    priority = Column(Enum(ProjectPriority), nullable=True, default=ProjectPriority.MEDIUM)

    # Timeline
    start_date = Column(Date, nullable=True)
    end_date = Column(Date, nullable=True)          # Estimated end
    actual_end_date = Column(Date, nullable=True)   # Set when completed

    # Budget & Billing
    budget_hours = Column(Numeric(8, 2), nullable=True)    # Planned hours
    consumed_hours = Column(Numeric(8, 2), default=0)      # Auto-updated from entries
    billable_hours = Column(Numeric(8, 2), default=0)      # Billable subset
    budget_amount = Column(Numeric(12, 2), nullable=True)  # Financial budget
    billing_rate = Column(Numeric(10, 2), nullable=True)   # Per-hour rate (overrides client)
    billing_type = Column(Enum(BillingType), nullable=True, default=BillingType.HOURLY)

    # Ownership
    project_manager_id = Column(Integer, ForeignKey("employees.id"), nullable=True, index=True)
    department_id = Column(Integer, ForeignKey("departments.id"), nullable=True)

    # UI
    color_code = Column(String(20), nullable=True)
    tags = Column(JSON, nullable=True)

    # Flags
    is_active = Column(Boolean, default=True, index=True)
    is_deleted = Column(Boolean, default=False, nullable=False)
    deleted_at = Column(DateTime, nullable=True)

    # Audit
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    created_by = Column(Integer, ForeignKey("employees.id"), nullable=True)

    # Relationships
    client = relationship("ProjectClient", back_populates="projects")
    project_manager = relationship("Employee", foreign_keys=[project_manager_id])
    members = relationship("ProjectMember", back_populates="project", cascade="all, delete-orphan")
    tasks = relationship("ProjectTask", back_populates="project", cascade="all, delete-orphan")

    __table_args__ = (
        UniqueConstraint("organization_id", "project_code", name="uq_project_org_code"),
        Index("idx_project_org_status", "organization_id", "status"),
        Index("idx_project_client", "client_id", "status"),
        Index("idx_project_manager", "project_manager_id"),
    )

    @property
    def budget_burn_percentage(self):
        """Percentage of budget hours consumed"""
        if self.budget_hours and float(self.budget_hours) > 0:
            return round(float(self.consumed_hours or 0) / float(self.budget_hours) * 100, 1)
        return None

    @property
    def remaining_hours(self):
        """Remaining budget hours"""
        if self.budget_hours is not None:
            return round(float(self.budget_hours) - float(self.consumed_hours or 0), 2)
        return None


# ============================================================
# MODULE 3: PROJECT TASK MASTER
# ============================================================

class ProjectTask(Base):
    """Tasks within a project — required for timesheet entries"""
    __tablename__ = "project_tasks"

    id = Column(Integer, primary_key=True, index=True)
    uuid = Column(GUID(as_uuid=True), default=uuid.uuid4, unique=True, nullable=False, index=True)
    organization_id = Column(Integer, ForeignKey("organization.id"), nullable=False, index=True)

    # Hierarchy
    project_id = Column(Integer, ForeignKey("projects.id"), nullable=False, index=True)
    parent_task_id = Column(Integer, ForeignKey("project_tasks.id"), nullable=True, index=True)  # Sub-tasks

    # Identity
    task_code = Column(String(50), nullable=True, index=True)
    task_name = Column(String(300), nullable=False)
    description = Column(Text, nullable=True)

    # Classification
    status = Column(Enum(TaskStatus), nullable=False, default=TaskStatus.TODO, index=True)
    priority = Column(Enum(ProjectPriority), nullable=True, default=ProjectPriority.MEDIUM)
    task_type = Column(Enum(TaskType), nullable=True, default=TaskType.FEATURE)

    # Assignment
    assigned_to_id = Column(Integer, ForeignKey("employees.id"), nullable=True, index=True)

    # Time Tracking (auto-updated)
    estimated_hours = Column(Numeric(6, 2), nullable=True)
    logged_hours = Column(Numeric(6, 2), default=0)        # Total hours logged
    billable_hours = Column(Numeric(6, 2), default=0)

    # Timeline
    start_date = Column(Date, nullable=True)
    due_date = Column(Date, nullable=True)
    completed_at = Column(DateTime, nullable=True)

    # Billing
    is_billable = Column(Boolean, nullable=True)  # Null = inherit from project

    # Metadata
    tags = Column(JSON, nullable=True)

    # Audit
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    created_by = Column(Integer, ForeignKey("employees.id"), nullable=True)
    is_deleted = Column(Boolean, default=False, nullable=False)
    deleted_at = Column(DateTime, nullable=True)

    # Relationships
    project = relationship("Project", back_populates="tasks")
    parent_task = relationship("ProjectTask", remote_side=[id])
    sub_tasks = relationship("ProjectTask", back_populates="parent_task")
    assigned_to = relationship("Employee", foreign_keys=[assigned_to_id])

    __table_args__ = (
        Index("idx_task_project_status", "project_id", "status"),
        Index("idx_task_assigned", "assigned_to_id", "status"),
        Index("idx_task_org", "organization_id", "status"),
    )


# ============================================================
# MODULE 4: PROJECT MEMBERS
# ============================================================

class ProjectMember(Base):
    """Controls which employees can log time to a project (enforced)"""
    __tablename__ = "project_members"

    id = Column(Integer, primary_key=True, index=True)
    uuid = Column(GUID(as_uuid=True), default=uuid.uuid4, unique=True, nullable=False)

    project_id = Column(Integer, ForeignKey("projects.id"), nullable=False, index=True)
    employee_id = Column(Integer, ForeignKey("employees.id"), nullable=False, index=True)

    # Role in project
    role = Column(Enum(MemberRole), nullable=False, default=MemberRole.DEVELOPER)

    # Billing override (per-member)
    billing_rate = Column(Numeric(10, 2), nullable=True)  # Overrides project rate

    # Hour allocation
    allocated_hours = Column(Numeric(6, 2), nullable=True)
    logged_hours = Column(Numeric(6, 2), default=0)        # Auto-updated

    # Membership period
    joined_at = Column(Date, nullable=True)
    left_at = Column(Date, nullable=True)

    is_active = Column(Boolean, default=True, index=True)

    # Audit
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    created_by = Column(Integer, ForeignKey("employees.id"), nullable=True)

    # Relationships
    project = relationship("Project", back_populates="members")
    employee = relationship("Employee", foreign_keys=[employee_id])

    __table_args__ = (
        UniqueConstraint("project_id", "employee_id", name="uq_project_member"),
        Index("idx_member_project_active", "project_id", "is_active"),
        Index("idx_member_employee", "employee_id", "is_active"),
    )


# ============================================================
# MODULE 5: ACTIVITY TYPE MASTER
# ============================================================

class ActivityType(Base):
    """Categories of work (Development, Testing, Meetings, etc.)"""
    __tablename__ = "activity_types"

    id = Column(Integer, primary_key=True, index=True)
    uuid = Column(GUID(as_uuid=True), default=uuid.uuid4, unique=True, nullable=False, index=True)
    organization_id = Column(Integer, ForeignKey("organization.id"), nullable=False, index=True)

    activity_code = Column(String(50), nullable=False, index=True)
    activity_name = Column(String(150), nullable=False)
    description = Column(Text, nullable=True)

    # Default billing behaviour for this activity
    is_billable_default = Column(Boolean, default=True)

    # UI
    color_code = Column(String(20), nullable=True)

    is_active = Column(Boolean, default=True, index=True)

    # Audit
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    created_by = Column(Integer, ForeignKey("employees.id"), nullable=True)
    is_deleted = Column(Boolean, default=False, nullable=False)

    __table_args__ = (
        UniqueConstraint("organization_id", "activity_code", name="uq_activity_org_code"),
        Index("idx_activity_org_active", "organization_id", "is_active"),
    )


# ============================================================
# MODULE 6: TIMESHEET POLICY
# ============================================================

class TimesheetPolicy(Base):
    """Org-level rules governing timesheet submission behaviour"""
    __tablename__ = "timesheet_policies"

    id = Column(Integer, primary_key=True, index=True)
    uuid = Column(GUID(as_uuid=True), default=uuid.uuid4, unique=True, nullable=False, index=True)
    organization_id = Column(Integer, ForeignKey("organization.id"), nullable=False, index=True)

    policy_name = Column(String(150), nullable=False)
    description = Column(Text, nullable=True)

    # Period
    period_type = Column(Enum(TimesheetPeriodType), nullable=False, default=TimesheetPeriodType.WEEKLY)
    submission_deadline_days = Column(Integer, default=3)   # Days after period end to submit

    # Hour constraints
    max_hours_per_day = Column(Numeric(4, 2), default=24)
    min_hours_per_day = Column(Numeric(4, 2), default=0)

    # Mandatory fields
    require_task_selection = Column(Boolean, default=True)      # Task is required
    require_activity_type = Column(Boolean, default=False)

    # Date rules
    allow_future_entries = Column(Boolean, default=False)       # Cannot log future hours
    allow_backdated_days = Column(Integer, default=7)           # How many past days allowed

    # Automation
    auto_submit = Column(Boolean, default=False)                # Auto-submit on deadline

    # Applicability
    applicable_to = Column(Enum(PolicyApplicableTo), default=PolicyApplicableTo.ALL)
    department_ids = Column(JSON, nullable=True)
    employee_type_ids = Column(JSON, nullable=True)

    is_active = Column(Boolean, default=True, index=True)
    is_default = Column(Boolean, default=False)
    effective_from = Column(Date, nullable=True)

    # Audit
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    created_by = Column(Integer, ForeignKey("employees.id"), nullable=True)
    is_deleted = Column(Boolean, default=False, nullable=False)

    __table_args__ = (
        Index("idx_ts_policy_org_active", "organization_id", "is_active"),
    )
