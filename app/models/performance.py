import uuid
import enum
from datetime import datetime, date
from sqlalchemy import (
    Column, Integer, String, Text, Boolean, DateTime, Date, Time,
    Numeric, ForeignKey, Enum, JSON, UniqueConstraint, Index,
    SmallInteger, Float
)
from sqlalchemy.orm import relationship
from app.db.base_class import Base
from app.models.organization import GUID

# ============================================================
# ENUMS
# ============================================================

class GoalFrameworkType(str, enum.Enum):
    OKR = "OKR"             # Objectives & Key Results
    SMART = "SMART"         # Specific, Measurable, Achievable, Relevant, Time-bound
    KPI = "KPI"             # Key Performance Indicators
    CUSTOM = "CUSTOM"


class GoalStatus(str, enum.Enum):
    DRAFT = "DRAFT"
    ACTIVE = "ACTIVE"
    ON_TRACK = "ON_TRACK"
    AT_RISK = "AT_RISK"
    BEHIND = "BEHIND"
    COMPLETED = "COMPLETED"
    CANCELLED = "CANCELLED"


class GoalType(str, enum.Enum):
    ORGANIZATION = "ORGANIZATION"
    DEPARTMENT = "DEPARTMENT"
    TEAM = "TEAM"
    INDIVIDUAL = "INDIVIDUAL"


class GoalMeasurementType(str, enum.Enum):
    NUMERIC = "NUMERIC"         # e.g., Revenue: 1,000,000
    PERCENTAGE = "PERCENTAGE"   # e.g., Customer satisfaction: 95%
    BOOLEAN = "BOOLEAN"         # Completed / Not completed
    MILESTONE = "MILESTONE"     # Milestone-based tracking


class CycleFrequency(str, enum.Enum):
    ANNUAL = "ANNUAL"
    SEMI_ANNUAL = "SEMI_ANNUAL"
    QUARTERLY = "QUARTERLY"
    MONTHLY = "MONTHLY"
    CUSTOM = "CUSTOM"


class CycleStatus(str, enum.Enum):
    DRAFT = "DRAFT"
    ACTIVE = "ACTIVE"
    SELF_APPRAISAL = "SELF_APPRAISAL"
    MANAGER_REVIEW = "MANAGER_REVIEW"
    CALIBRATION = "CALIBRATION"
    COMPLETED = "COMPLETED"
    ARCHIVED = "ARCHIVED"


class AppraisalStatus(str, enum.Enum):
    NOT_STARTED = "NOT_STARTED"
    SELF_IN_PROGRESS = "SELF_IN_PROGRESS"
    SELF_SUBMITTED = "SELF_SUBMITTED"
    MANAGER_IN_PROGRESS = "MANAGER_IN_PROGRESS"
    MANAGER_SUBMITTED = "MANAGER_SUBMITTED"
    CALIBRATION_PENDING = "CALIBRATION_PENDING"
    CALIBRATED = "CALIBRATED"
    PUBLISHED = "PUBLISHED"
    ACKNOWLEDGED = "ACKNOWLEDGED"


class QuestionType(str, enum.Enum):
    RATING = "RATING"
    TEXT = "TEXT"
    MULTI_CHOICE = "MULTI_CHOICE"
    GOAL_RATING = "GOAL_RATING"
    COMPETENCY_RATING = "COMPETENCY_RATING"


class FeedbackRequestStatus(str, enum.Enum):
    PENDING = "PENDING"
    IN_PROGRESS = "IN_PROGRESS"
    COMPLETED = "COMPLETED"
    EXPIRED = "EXPIRED"


class FeedbackProviderType(str, enum.Enum):
    SELF = "SELF"
    PEER = "PEER"
    SUBORDINATE = "SUBORDINATE"
    SUPERVISOR = "SUPERVISOR"
    EXTERNAL = "EXTERNAL"


class PIPStatus(str, enum.Enum):
    DRAFT = "DRAFT"
    ACTIVE = "ACTIVE"
    ON_TRACK = "ON_TRACK"
    AT_RISK = "AT_RISK"
    COMPLETED_SUCCESS = "COMPLETED_SUCCESS"
    COMPLETED_FAILURE = "COMPLETED_FAILURE"
    WITHDRAWN = "WITHDRAWN"


class TalentCategory(str, enum.Enum):
    HIGH_POTENTIAL = "HIGH_POTENTIAL"
    HIGH_PERFORMER = "HIGH_PERFORMER"
    CORE_CONTRIBUTOR = "CORE_CONTRIBUTOR"
    NEEDS_IMPROVEMENT = "NEEDS_IMPROVEMENT"
    NEW_HIRE = "NEW_HIRE"


class NineBoxPosition(str, enum.Enum):
    # Performance (X) x Potential (Y)
    LOW_LOW = "LOW_LOW"
    LOW_MED = "LOW_MED"
    LOW_HIGH = "LOW_HIGH"
    MED_LOW = "MED_LOW"
    MED_MED = "MED_MED"
    MED_HIGH = "MED_HIGH"
    HIGH_LOW = "HIGH_LOW"
    HIGH_MED = "HIGH_MED"
    HIGH_HIGH = "HIGH_HIGH"


class NotificationType(str, enum.Enum):
    CYCLE_STARTED = "CYCLE_STARTED"
    SELF_APPRAISAL_DUE = "SELF_APPRAISAL_DUE"
    SELF_APPRAISAL_REMINDER = "SELF_APPRAISAL_REMINDER"
    MANAGER_REVIEW_DUE = "MANAGER_REVIEW_DUE"
    FEEDBACK_REQUEST = "FEEDBACK_REQUEST"
    FEEDBACK_REMINDER = "FEEDBACK_REMINDER"
    GOAL_DUE = "GOAL_DUE"
    APPRAISAL_PUBLISHED = "APPRAISAL_PUBLISHED"
    PIP_CREATED = "PIP_CREATED"
    ONE_ON_ONE_REMINDER = "ONE_ON_ONE_REMINDER"
    CALIBRATION_SCHEDULED = "CALIBRATION_SCHEDULED"


# ============================================================
# 1. GOAL MANAGEMENT
# ============================================================

class GoalFramework(Base):
    """Defines goal methodology frameworks available in the system."""
    __tablename__ = "goal_frameworks"

    id = Column(Integer, primary_key=True, autoincrement=True)
    uuid = Column(GUID(), default=uuid.uuid4, unique=True, nullable=False)
    organization_id = Column(Integer, ForeignKey("organization.id"), nullable=False, index=True)

    name = Column(String(100), nullable=False)                  # "OKR", "SMART Goals", "KPI Tracker"
    framework_type = Column(Enum(GoalFrameworkType), nullable=False)
    description = Column(Text, nullable=True)
    is_default = Column(Boolean, default=False)
    is_active = Column(Boolean, default=True)

    # OKR-specific config
    max_objectives_per_employee = Column(SmallInteger, default=5)
    max_key_results_per_objective = Column(SmallInteger, default=5)

    # SMART config
    require_specific = Column(Boolean, default=True)
    require_measurable = Column(Boolean, default=True)
    require_time_bound = Column(Boolean, default=True)

    # Scoring weights
    goal_weight_enabled = Column(Boolean, default=True)
    default_scoring_method = Column(String(50), default="weighted_average")

    created_by = Column(Integer, ForeignKey("employees.id"), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    organization = relationship("Organization")
    creator = relationship("Employee", foreign_keys=[created_by])

    __table_args__ = (
        UniqueConstraint("organization_id", "name", name="uq_goal_framework_org_name"),
        Index("idx_goal_framework_org", "organization_id", "is_active"),
    )


class OrganizationGoal(Base):
    """Top-level strategic organizational goals."""
    __tablename__ = "organization_goals"

    id = Column(Integer, primary_key=True, autoincrement=True)
    uuid = Column(GUID(), default=uuid.uuid4, unique=True, nullable=False)
    organization_id = Column(Integer, ForeignKey("organization.id"), nullable=False, index=True)
    framework_id = Column(Integer, ForeignKey("goal_frameworks.id"), nullable=False)

    title = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    goal_type = Column(Enum(GoalFrameworkType), nullable=False)

    # Time period
    start_date = Column(Date, nullable=False)
    end_date = Column(Date, nullable=False)
    fiscal_year = Column(String(10), nullable=True)          # "FY2025", "2025-Q2"

    # Measurement
    measurement_type = Column(Enum(GoalMeasurementType), nullable=False)
    target_value = Column(Numeric(15, 2), nullable=True)
    current_value = Column(Numeric(15, 2), default=0)
    unit = Column(String(50), nullable=True)                 # "$", "%", "units"

    # Status
    status = Column(Enum(GoalStatus), default=GoalStatus.DRAFT)
    status_notes = Column(Text, nullable=True)               # Notes recorded on last status change
    weight = Column(Numeric(5, 2), default=100.00)           # Relative importance %
    progress_percentage = Column(Numeric(5, 2), default=0)

    # Ownership
    owner_id = Column(Integer, ForeignKey("employees.id"), nullable=False)

    is_public = Column(Boolean, default=True)
    tags = Column(JSON, default=list)                        # ["Revenue", "Growth"]
    attachments = Column(JSON, default=list)

    created_by = Column(Integer, ForeignKey("employees.id"), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    organization = relationship("Organization")
    framework = relationship("GoalFramework")
    owner = relationship("Employee", foreign_keys=[owner_id])
    creator = relationship("Employee", foreign_keys=[created_by])

    __table_args__ = (
        Index("idx_org_goal_status_year", "organization_id", "status", "fiscal_year"),
    )


class DepartmentGoal(Base):
    """Department-level goals cascaded from organizational goals."""
    __tablename__ = "department_goals"

    id = Column(Integer, primary_key=True, autoincrement=True)
    uuid = Column(GUID(), default=uuid.uuid4, unique=True, nullable=False)
    organization_id = Column(Integer, ForeignKey("organization.id"), nullable=False)
    department_id = Column(Integer, ForeignKey("departments.id"), nullable=False, index=True)
    framework_id = Column(Integer, ForeignKey("goal_frameworks.id"), nullable=False)

    # Parent goal linkage (cascading)
    parent_org_goal_id = Column(Integer, ForeignKey("organization_goals.id"), nullable=True)

    title = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)

    start_date = Column(Date, nullable=False)
    end_date = Column(Date, nullable=False)
    fiscal_year = Column(String(10), nullable=True)

    measurement_type = Column(Enum(GoalMeasurementType), nullable=False)
    target_value = Column(Numeric(15, 2), nullable=True)
    current_value = Column(Numeric(15, 2), default=0)
    unit = Column(String(50), nullable=True)
    weight = Column(Numeric(5, 2), default=100.00)
    progress_percentage = Column(Numeric(5, 2), default=0)
    status = Column(Enum(GoalStatus), default=GoalStatus.DRAFT)

    owner_id = Column(Integer, ForeignKey("employees.id"), nullable=False)
    tags = Column(JSON, default=list)

    created_by = Column(Integer, ForeignKey("employees.id"), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    is_deleted = Column(Boolean, default=False, nullable=False)
    deleted_at = Column(DateTime, nullable=True)

    # Relationships
    organization = relationship("Organization")
    department = relationship("Department")
    framework = relationship("GoalFramework")
    parent_org_goal = relationship("OrganizationGoal")
    owner = relationship("Employee", foreign_keys=[owner_id])
    creator = relationship("Employee", foreign_keys=[created_by])

    __table_args__ = (
        Index("idx_dept_goal_dept_status", "department_id", "status"),
        Index("idx_dept_goal_parent", "parent_org_goal_id"),
    )


class EmployeeGoal(Base):
    """Individual employee goals, possibly cascaded from department/org goals."""
    __tablename__ = "employee_goals"

    id = Column(Integer, primary_key=True, autoincrement=True)
    uuid = Column(GUID(), default=uuid.uuid4, unique=True, nullable=False)
    organization_id = Column(Integer, ForeignKey("organization.id"), nullable=False)
    employee_id = Column(Integer, ForeignKey("employees.id"), nullable=False, index=True)
    framework_id = Column(Integer, ForeignKey("goal_frameworks.id"), nullable=False)

    # Cascading linkage
    parent_dept_goal_id = Column(Integer, ForeignKey("department_goals.id"), nullable=True)
    parent_org_goal_id = Column(Integer, ForeignKey("organization_goals.id"), nullable=True)
    appraisal_cycle_id = Column(Integer, ForeignKey("appraisal_cycles.id"), nullable=True)

    title = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)

    # SMART fields
    is_specific = Column(Boolean, default=False)
    is_measurable = Column(Boolean, default=False)
    is_achievable = Column(Boolean, default=False)
    is_relevant = Column(Boolean, default=False)
    is_time_bound = Column(Boolean, default=False)

    # OKR fields
    objective_key = Column(String(20), nullable=True)        # "O1", "KR1.1"
    is_key_result = Column(Boolean, default=False)
    parent_objective_id = Column(Integer, ForeignKey("employee_goals.id"), nullable=True)

    start_date = Column(Date, nullable=False)
    end_date = Column(Date, nullable=False)

    measurement_type = Column(Enum(GoalMeasurementType), nullable=False)
    target_value = Column(Numeric(15, 2), nullable=True)
    current_value = Column(Numeric(15, 2), default=0)
    baseline_value = Column(Numeric(15, 2), nullable=True)
    unit = Column(String(50), nullable=True)
    weight = Column(Numeric(5, 2), default=100.00)           # % of overall goal score

    status = Column(Enum(GoalStatus), default=GoalStatus.DRAFT)
    progress_percentage = Column(Numeric(5, 2), default=0)

    # Approval
    manager_id = Column(Integer, ForeignKey("employees.id"), nullable=True)
    approved_by = Column(Integer, ForeignKey("employees.id"), nullable=True)
    approved_at = Column(DateTime, nullable=True)
    manager_comment = Column(Text, nullable=True)

    # Scoring (post-appraisal)
    achieved_value = Column(Numeric(15, 2), nullable=True)
    achievement_percentage = Column(Numeric(5, 2), nullable=True)
    goal_score = Column(Numeric(5, 2), nullable=True)        # Weighted score

    is_stretch_goal = Column(Boolean, default=False)
    tags = Column(JSON, default=list)
    attachments = Column(JSON, default=list)

    is_deleted = Column(Boolean, default=False, nullable=False, index=True)

    created_by = Column(Integer, ForeignKey("employees.id"), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    organization = relationship("Organization")
    employee = relationship("Employee", foreign_keys=[employee_id])
    framework = relationship("GoalFramework")
    parent_dept_goal = relationship("DepartmentGoal")
    parent_org_goal = relationship("OrganizationGoal")
    appraisal_cycle = relationship("AppraisalCycle")
    parent_objective = relationship("EmployeeGoal", remote_side=[id], foreign_keys=[parent_objective_id])
    manager = relationship("Employee", foreign_keys=[manager_id])
    approved_by_employee = relationship("Employee", foreign_keys=[approved_by])
    creator = relationship("Employee", foreign_keys=[created_by])

    @property
    def employee_uuid(self):
        return self.employee.uuid if self.employee else None
        
    @property
    def framework_uuid(self):
        return self.framework.uuid if self.framework else None
        
    @property
    def parent_dept_goal_uuid(self):
        return self.parent_dept_goal.uuid if self.parent_dept_goal else None
        
    @property
    def parent_org_goal_uuid(self):
        return self.parent_org_goal.uuid if self.parent_org_goal else None
        
    @property
    def parent_dept_goal_title(self):
        return self.parent_dept_goal.title if self.parent_dept_goal else None
        
    @property
    def parent_org_goal_title(self):
        return self.parent_org_goal.title if self.parent_org_goal else None
        
    @property
    def appraisal_cycle_uuid(self):
        return self.appraisal_cycle.uuid if self.appraisal_cycle else None
        
    @property
    def parent_objective_uuid(self):
        return self.parent_objective.uuid if self.parent_objective else None

    __table_args__ = (
        Index("idx_emp_goal_emp_status", "employee_id", "status"),
        Index("idx_emp_goal_cycle", "appraisal_cycle_id", "employee_id"),
        Index("idx_emp_goal_parent_dept", "parent_dept_goal_id"),
    )


class GoalProgress(Base):
    """Tracks periodic progress updates on employee goals."""
    __tablename__ = "goal_progress"

    id = Column(Integer, primary_key=True, autoincrement=True)
    uuid = Column(GUID(), default=uuid.uuid4, unique=True, nullable=False)
    employee_goal_id = Column(Integer, ForeignKey("employee_goals.id"), nullable=False, index=True)
    employee_id = Column(Integer, ForeignKey("employees.id"), nullable=False)

    check_in_date = Column(Date, nullable=False, default=date.today)
    current_value = Column(Numeric(15, 2), nullable=True)
    progress_percentage = Column(Numeric(5, 2), nullable=False)
    status = Column(Enum(GoalStatus), nullable=False)

    # Narrative
    update_notes = Column(Text, nullable=True)
    blockers = Column(Text, nullable=True)
    next_steps = Column(Text, nullable=True)

    # Manager acknowledgment
    acknowledged_by = Column(Integer, ForeignKey("employees.id"), nullable=True)
    acknowledged_at = Column(DateTime, nullable=True)
    manager_comment = Column(Text, nullable=True)

    attachments = Column(JSON, default=list)

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    employee_goal = relationship("EmployeeGoal")
    employee = relationship("Employee", foreign_keys=[employee_id])
    acknowledged_by_employee = relationship("Employee", foreign_keys=[acknowledged_by])

    __table_args__ = (
        Index("idx_goal_progress_goal_date", "employee_goal_id", "check_in_date"),
    )


class GoalAlignment(Base):
    """Explicit mapping table for goal cascading / alignment hierarchy."""
    __tablename__ = "goal_alignments"

    id = Column(Integer, primary_key=True, autoincrement=True)
    organization_id = Column(Integer, ForeignKey("organization.id"), nullable=False)

    # Parent can be org, dept, or employee goal
    parent_goal_type = Column(Enum(GoalType), nullable=False)
    parent_goal_id = Column(Integer, nullable=False)         # FK resolved by type

    child_goal_type = Column(Enum(GoalType), nullable=False)
    child_goal_id = Column(Integer, nullable=False)

    alignment_weight = Column(Numeric(5, 2), default=100.00) # % contribution to parent
    notes = Column(Text, nullable=True)

    created_by = Column(Integer, ForeignKey("employees.id"), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    organization = relationship("Organization")
    creator = relationship("Employee", foreign_keys=[created_by])

    __table_args__ = (
        UniqueConstraint("parent_goal_type", "parent_goal_id", "child_goal_type", "child_goal_id",
                         name="uq_goal_alignment"),
        Index("idx_goal_align_parent", "parent_goal_type", "parent_goal_id"),
        Index("idx_goal_align_child", "child_goal_type", "child_goal_id"),
    )


# ============================================================
# 2. APPRAISAL CONFIGURATION
# ============================================================

class AppraisalCycle(Base):
    """Defines appraisal review cycles (annual, semi-annual, quarterly)."""
    __tablename__ = "appraisal_cycles"

    id = Column(Integer, primary_key=True, autoincrement=True)
    uuid = Column(GUID(), default=uuid.uuid4, unique=True, nullable=False)
    organization_id = Column(Integer, ForeignKey("organization.id"), nullable=False, index=True)

    name = Column(String(150), nullable=False)                # "Annual Review 2025", "Q3 2025"
    frequency = Column(Enum(CycleFrequency), nullable=False)
    fiscal_year = Column(String(10), nullable=True)

    # Review period (what's being evaluated)
    review_period_start = Column(Date, nullable=False)
    review_period_end = Column(Date, nullable=False)

    # Phase windows
    goal_setting_start = Column(Date, nullable=True)
    goal_setting_end = Column(Date, nullable=True)
    self_appraisal_start = Column(Date, nullable=False)
    self_appraisal_end = Column(Date, nullable=False)
    manager_review_start = Column(Date, nullable=False)
    manager_review_end = Column(Date, nullable=False)
    calibration_start = Column(Date, nullable=True)
    calibration_end = Column(Date, nullable=True)
    result_publication_date = Column(Date, nullable=True)

    status = Column(Enum(CycleStatus), default=CycleStatus.DRAFT)
    template_id = Column(Integer, ForeignKey("appraisal_templates.id"), nullable=False)
    rating_scale_id = Column(Integer, ForeignKey("rating_scales.id"), nullable=False)

    # Eligibility criteria
    include_probationary = Column(Boolean, default=False)
    minimum_tenure_days = Column(Integer, default=90)
    applicable_departments = Column(JSON, default=list)      # [] = all departments
    applicable_employee_types = Column(JSON, default=list)   # [] = all types

    # Workflow config
    require_self_appraisal = Column(Boolean, default=True)
    require_360_feedback = Column(Boolean, default=False)
    require_calibration = Column(Boolean, default=False)
    allow_employee_acknowledgment = Column(Boolean, default=True)

    # Bell curve config
    bell_curve_enabled = Column(Boolean, default=False)
    bell_curve_config = Column(JSON, nullable=True)          # {"Outstanding": 10, "Exceeds": 20, ...}

    # Notifications
    reminders_enabled = Column(Boolean, default=True)
    reminder_days_before = Column(JSON, default=[7, 3, 1])   # Days before deadline

    created_by = Column(Integer, ForeignKey("employees.id"), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # History
    advance_history = Column(JSON, default=list)

    # Relationships
    organization = relationship("Organization")
    template = relationship("AppraisalTemplate", foreign_keys=[template_id])
    rating_scale = relationship("RatingScale", foreign_keys=[rating_scale_id])
    creator = relationship("Employee", foreign_keys=[created_by])

    @property
    def template_uuid(self):
        return self.template.uuid if self.template else None

    @property
    def rating_scale_uuid(self):
        return self.rating_scale.uuid if self.rating_scale else None

    __table_args__ = (
        UniqueConstraint("organization_id", "name", name="uq_appraisal_cycle_name"),
        Index("idx_appraisal_cycle_org_status", "organization_id", "status"),
    )


class RatingScale(Base):
    """Defines rating scale options used across appraisal templates."""
    __tablename__ = "rating_scales"

    id = Column(Integer, primary_key=True, autoincrement=True)
    uuid = Column(GUID(), default=uuid.uuid4, unique=True, nullable=False)
    organization_id = Column(Integer, ForeignKey("organization.id"), nullable=False, index=True)

    name = Column(String(100), nullable=False)                # "5-Point Rating Scale", "A-E Grade"
    description = Column(Text, nullable=True)
    is_default = Column(Boolean, default=False)
    is_active = Column(Boolean, default=True)

    # Scale points stored as ordered JSON
    # [{"value": 5, "label": "Outstanding", "description": "...", "color": "#00AA00", "is_passing": True}]
    scale_points = Column(JSON, nullable=False)

    min_value = Column(Numeric(5, 2), nullable=False)
    max_value = Column(Numeric(5, 2), nullable=False)

    created_by = Column(Integer, ForeignKey("employees.id"), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    organization = relationship("Organization")
    creator = relationship("Employee", foreign_keys=[created_by])

    __table_args__ = (
        UniqueConstraint("organization_id", "name", name="uq_rating_scale_name"),
    )


class AppraisalTemplate(Base):
    """Reusable evaluation form templates for appraisal cycles."""
    __tablename__ = "appraisal_templates"

    id = Column(Integer, primary_key=True, autoincrement=True)
    uuid = Column(GUID(), default=uuid.uuid4, unique=True, nullable=False)
    organization_id = Column(Integer, ForeignKey("organization.id"), nullable=False, index=True)
    rating_scale_id = Column(Integer, ForeignKey("rating_scales.id"), nullable=False)

    name = Column(String(150), nullable=False)
    description = Column(Text, nullable=True)
    is_active = Column(Boolean, default=True)
    is_default = Column(Boolean, default=False)

    # Applicable roles/levels
    applicable_roles = Column(JSON, default=list)
    applicable_departments = Column(JSON, default=list)
    applicable_grades = Column(JSON, default=list)

    # Section weights
    goal_section_weight = Column(Numeric(5, 2), default=40.00)
    competency_section_weight = Column(Numeric(5, 2), default=30.00)
    behavior_section_weight = Column(Numeric(5, 2), default=20.00)
    other_section_weight = Column(Numeric(5, 2), default=10.00)

    # Self-appraisal config
    self_appraisal_enabled = Column(Boolean, default=True)
    self_rating_visible_to_manager = Column(Boolean, default=True)
    employee_comments_enabled = Column(Boolean, default=True)

    # Manager config
    manager_override_enabled = Column(Boolean, default=True)
    final_rating_formula = Column(String(100), default="weighted_average")

    version = Column(SmallInteger, default=1)
    cloned_from_id = Column(Integer, ForeignKey("appraisal_templates.id"), nullable=True)

    created_by = Column(Integer, ForeignKey("employees.id"), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    organization = relationship("Organization")
    rating_scale = relationship("RatingScale", foreign_keys=[rating_scale_id])
    cloned_from = relationship("AppraisalTemplate", remote_side=[id], foreign_keys=[cloned_from_id])
    creator = relationship("Employee", foreign_keys=[created_by])

    __table_args__ = (
        UniqueConstraint("organization_id", "name", name="uq_appraisal_template_name"),
        Index("idx_appraisal_template_org", "organization_id", "is_active"),
    )


class AppraisalSection(Base):
    """Sections within an appraisal template (Goals, Competencies, Behavior, etc.)."""
    __tablename__ = "appraisal_sections"

    id = Column(Integer, primary_key=True, autoincrement=True)
    uuid = Column(GUID(), default=uuid.uuid4, unique=True, nullable=False)
    template_id = Column(Integer, ForeignKey("appraisal_templates.id"), nullable=False, index=True)

    title = Column(String(150), nullable=False)
    description = Column(Text, nullable=True)
    section_order = Column(SmallInteger, nullable=False)
    weight = Column(Numeric(5, 2), nullable=False)           # % of total score

    # Section type determines rendering behavior
    section_type = Column(String(50), nullable=False)        # "goals", "competency", "behavior", "custom"

    is_required = Column(Boolean, default=True)
    instructions = Column(Text, nullable=True)

    # Visibility
    visible_to_employee = Column(Boolean, default=True)
    visible_to_manager = Column(Boolean, default=True)

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    template = relationship("AppraisalTemplate")

    __table_args__ = (
        UniqueConstraint("template_id", "section_order", name="uq_section_order"),
        Index("idx_appraisal_section_template", "template_id"),
    )


class AppraisalQuestion(Base):
    """Questions/criteria within each appraisal section."""
    __tablename__ = "appraisal_questions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    uuid = Column(GUID(), default=uuid.uuid4, unique=True, nullable=False)
    section_id = Column(Integer, ForeignKey("appraisal_sections.id"), nullable=False, index=True)

    question_text = Column(Text, nullable=False)
    question_type = Column(Enum(QuestionType), nullable=False)
    question_order = Column(SmallInteger, nullable=False)

    is_required = Column(Boolean, default=True)
    weight = Column(Numeric(5, 2), default=100.00)           # Within section

    # Rating question config
    use_section_rating_scale = Column(Boolean, default=True)
    custom_rating_scale_id = Column(Integer, ForeignKey("rating_scales.id"), nullable=True)

    # Multi-choice config
    choices = Column(JSON, default=list)                     # [{"value": "a", "label": "Option A"}]
    allow_multiple_selection = Column(Boolean, default=False)

    # Competency linkage
    competency_id = Column(Integer, ForeignKey("competency_frameworks.id"), nullable=True)

    # Goal-rating linkage (auto-populated from employee goals)
    auto_populate_goals = Column(Boolean, default=False)

    guidance = Column(Text, nullable=True)                   # Guidance text for answerers
    placeholder_text = Column(String(255), nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    section = relationship("AppraisalSection")
    custom_rating_scale = relationship("RatingScale", foreign_keys=[custom_rating_scale_id])
    competency = relationship("CompetencyFramework")

    __table_args__ = (
        UniqueConstraint("section_id", "question_order", name="uq_question_order"),
    )


# ============================================================
# 3. APPRAISAL PROCESS
# ============================================================

class AppraisalRecord(Base):
    """Master appraisal record per employee per cycle."""
    __tablename__ = "appraisal_records"

    id = Column(Integer, primary_key=True, autoincrement=True)
    uuid = Column(GUID(), default=uuid.uuid4, unique=True, nullable=False)
    organization_id = Column(Integer, ForeignKey("organization.id"), nullable=False)
    appraisal_cycle_id = Column(Integer, ForeignKey("appraisal_cycles.id"), nullable=False, index=True)
    employee_id = Column(Integer, ForeignKey("employees.id"), nullable=False, index=True)
    manager_id = Column(Integer, ForeignKey("employees.id"), nullable=True)
    template_id = Column(Integer, ForeignKey("appraisal_templates.id"), nullable=False)
    rating_scale_id = Column(Integer, ForeignKey("rating_scales.id"), nullable=False)

    status = Column(Enum(AppraisalStatus), default=AppraisalStatus.NOT_STARTED, index=True)

    # Computed scores
    self_goal_score = Column(Numeric(5, 2), nullable=True)
    self_competency_score = Column(Numeric(5, 2), nullable=True)
    self_overall_score = Column(Numeric(5, 2), nullable=True)
    self_rating_label = Column(String(50), nullable=True)     # "Meets Expectations"

    manager_goal_score = Column(Numeric(5, 2), nullable=True)
    manager_competency_score = Column(Numeric(5, 2), nullable=True)
    manager_overall_score = Column(Numeric(5, 2), nullable=True)
    manager_rating_label = Column(String(50), nullable=True)

    # Post-calibration final rating
    final_score = Column(Numeric(5, 2), nullable=True)
    final_rating_label = Column(String(50), nullable=True)
    calibrated_score = Column(Numeric(5, 2), nullable=True)
    calibrated_by = Column(Integer, ForeignKey("employees.id"), nullable=True)
    calibrated_at = Column(DateTime, nullable=True)
    calibration_notes = Column(Text, nullable=True)

    # Timeline tracking
    self_appraisal_submitted_at = Column(DateTime, nullable=True)
    manager_review_submitted_at = Column(DateTime, nullable=True)
    published_at = Column(DateTime, nullable=True)
    published_by = Column(Integer, ForeignKey("employees.id"), nullable=True)

    # Employee acknowledgment
    acknowledged_by_employee = Column(Boolean, default=False)
    employee_acknowledged_at = Column(DateTime, nullable=True)
    employee_disagreement_reason = Column(Text, nullable=True)

    # 360 feedback summary
    has_360_feedback = Column(Boolean, default=False)
    feedback_360_score = Column(Numeric(5, 2), nullable=True)

    # Compensation / promotion link
    compensation_action_triggered = Column(Boolean, default=False)
    promotion_recommended = Column(Boolean, default=False)
    promotion_recommended_to_grade = Column(String(50), nullable=True)

    is_active = Column(Boolean, default=True)
    notes = Column(Text, nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    organization = relationship("Organization")
    appraisal_cycle = relationship("AppraisalCycle")
    employee = relationship("Employee", foreign_keys=[employee_id])
    manager = relationship("Employee", foreign_keys=[manager_id])
    template = relationship("AppraisalTemplate", foreign_keys=[template_id])
    rating_scale = relationship("RatingScale", foreign_keys=[rating_scale_id])
    calibrator = relationship("Employee", foreign_keys=[calibrated_by])
    publisher = relationship("Employee", foreign_keys=[published_by])

    __table_args__ = (
        UniqueConstraint("appraisal_cycle_id", "employee_id", name="uq_appraisal_per_cycle"),
        Index("idx_appraisal_record_cycle_status", "appraisal_cycle_id", "status"),
        Index("idx_appraisal_record_manager", "manager_id", "status"),
    )


class SelfAppraisal(Base):
    """Employee self-evaluation form submission."""
    __tablename__ = "self_appraisals"

    id = Column(Integer, primary_key=True, autoincrement=True)
    uuid = Column(GUID(), default=uuid.uuid4, unique=True, nullable=False)
    appraisal_record_id = Column(Integer, ForeignKey("appraisal_records.id"), nullable=False, unique=True)
    employee_id = Column(Integer, ForeignKey("employees.id"), nullable=False, index=True)

    # Narrative commentary
    achievements_summary = Column(Text, nullable=True)
    challenges_faced = Column(Text, nullable=True)
    learning_development = Column(Text, nullable=True)
    career_aspirations = Column(Text, nullable=True)
    support_needed = Column(Text, nullable=True)

    # Status
    is_submitted = Column(Boolean, default=False)
    submitted_at = Column(DateTime, nullable=True)
    last_saved_at = Column(DateTime, nullable=True)

    # Draft auto-save token
    draft_version = Column(Integer, default=1)

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    appraisal_record = relationship("AppraisalRecord")
    employee = relationship("Employee")

    @property
    def appraisal_record_uuid(self):
        return self.appraisal_record.uuid if self.appraisal_record else None

    __table_args__ = (
        Index("idx_self_appraisal_employee", "employee_id"),
    )


class ManagerAppraisal(Base):
    """Manager evaluation form for an employee."""
    __tablename__ = "manager_appraisals"

    id = Column(Integer, primary_key=True, autoincrement=True)
    uuid = Column(GUID(), default=uuid.uuid4, unique=True, nullable=False)
    appraisal_record_id = Column(Integer, ForeignKey("appraisal_records.id"), nullable=False, unique=True)
    manager_id = Column(Integer, ForeignKey("employees.id"), nullable=True, index=True)
    employee_id = Column(Integer, ForeignKey("employees.id"), nullable=False)

    # Narrative
    performance_summary = Column(Text, nullable=True)
    strengths = Column(Text, nullable=True)
    areas_for_improvement = Column(Text, nullable=True)
    development_plan = Column(Text, nullable=True)
    promotion_recommendation = Column(Text, nullable=True)

    # Calibration override notes
    override_reason = Column(Text, nullable=True)

    is_submitted = Column(Boolean, default=False)
    submitted_at = Column(DateTime, nullable=True)
    last_saved_at = Column(DateTime, nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    appraisal_record = relationship("AppraisalRecord")
    manager = relationship("Employee", foreign_keys=[manager_id])
    employee = relationship("Employee", foreign_keys=[employee_id])

    @property
    def appraisal_record_uuid(self):
        return self.appraisal_record.uuid if self.appraisal_record else None

    __table_args__ = (
        Index("idx_manager_appraisal_manager", "manager_id"),
    )


class AppraisalAnswer(Base):
    """Individual question answers (rating + text) for self and manager appraisals."""
    __tablename__ = "appraisal_answers"

    id = Column(Integer, primary_key=True, autoincrement=True)
    uuid = Column(GUID(), default=uuid.uuid4, unique=True, nullable=False)
    appraisal_record_id = Column(Integer, ForeignKey("appraisal_records.id"), nullable=False, index=True)
    question_id = Column(Integer, ForeignKey("appraisal_questions.id"), nullable=False)

    # Who answered
    respondent_type = Column(String(20), nullable=False)     # "self", "manager"
    respondent_id = Column(Integer, ForeignKey("employees.id"), nullable=False)

    # Answer data (polymorphic storage)
    rating_value = Column(Numeric(5, 2), nullable=True)
    rating_label = Column(String(100), nullable=True)
    text_answer = Column(Text, nullable=True)
    selected_choices = Column(JSON, default=list)

    # Goal-specific
    goal_id = Column(Integer, ForeignKey("employee_goals.id"), nullable=True)
    goal_achievement_percentage = Column(Numeric(5, 2), nullable=True)

    # Competency-specific
    competency_id = Column(Integer, ForeignKey("competency_frameworks.id"), nullable=True)

    weight_applied = Column(Numeric(5, 2), nullable=True)
    weighted_score = Column(Numeric(5, 2), nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    appraisal_record = relationship("AppraisalRecord")
    question = relationship("AppraisalQuestion")
    respondent = relationship("Employee", foreign_keys=[respondent_id])
    goal = relationship("EmployeeGoal")
    competency = relationship("CompetencyFramework")

    __table_args__ = (
        UniqueConstraint("appraisal_record_id", "question_id", "respondent_type",
                         name="uq_appraisal_answer"),
        Index("idx_appraisal_answer_record", "appraisal_record_id", "respondent_type"),
    )


class AppraisalCalibration(Base):
    """Calibration session to normalize ratings across teams/departments."""
    __tablename__ = "appraisal_calibrations"

    id = Column(Integer, primary_key=True, autoincrement=True)
    uuid = Column(GUID(), default=uuid.uuid4, unique=True, nullable=False)
    organization_id = Column(Integer, ForeignKey("organization.id"), nullable=False)
    appraisal_cycle_id = Column(Integer, ForeignKey("appraisal_cycles.id"), nullable=False, index=True)

    name = Column(String(150), nullable=False)                # "Engineering Calibration - Q4 2025"
    department_id = Column(Integer, ForeignKey("departments.id"), nullable=True)

    # Session logistics
    scheduled_date = Column(DateTime, nullable=True)
    conducted_date = Column(DateTime, nullable=True)
    facilitator_id = Column(Integer, ForeignKey("employees.id"), nullable=False)

    # Bell curve / normalization
    target_distribution = Column(JSON, nullable=True)         # {"Outstanding": 10, "Exceeds": 20, ...}
    actual_distribution = Column(JSON, nullable=True)         # Computed after calibration

    status = Column(String(30), default="SCHEDULED")          # SCHEDULED, IN_PROGRESS, COMPLETED
    session_notes = Column(Text, nullable=True)
    meeting_minutes = Column(Text, nullable=True)

    created_by = Column(Integer, ForeignKey("employees.id"), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    organization = relationship("Organization")
    appraisal_cycle = relationship("AppraisalCycle")
    department = relationship("Department")
    facilitator = relationship("Employee", foreign_keys=[facilitator_id])
    creator = relationship("Employee", foreign_keys=[created_by])

    __table_args__ = (
        Index("idx_calibration_cycle_dept", "appraisal_cycle_id", "department_id"),
    )


class CalibrationParticipant(Base):
    """Managers/HR involved in a calibration session."""
    __tablename__ = "calibration_participants"

    id = Column(Integer, primary_key=True, autoincrement=True)
    calibration_id = Column(Integer, ForeignKey("appraisal_calibrations.id"), nullable=False, index=True)
    participant_id = Column(Integer, ForeignKey("employees.id"), nullable=False)

    role = Column(String(50), nullable=False)                 # "facilitator", "reviewer", "hr_observer"
    attended = Column(Boolean, default=False)
    joined_at = Column(DateTime, nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    calibration = relationship("AppraisalCalibration")
    participant = relationship("Employee")

    __table_args__ = (
        UniqueConstraint("calibration_id", "participant_id", name="uq_calibration_participant"),
    )


class BellCurveDistribution(Base):
    """Stores the normalization/bell curve distribution for a cycle per org/department."""
    __tablename__ = "bell_curve_distributions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    uuid = Column(GUID(), default=uuid.uuid4, unique=True, nullable=False)
    appraisal_cycle_id = Column(Integer, ForeignKey("appraisal_cycles.id"), nullable=False, index=True)
    department_id = Column(Integer, ForeignKey("departments.id"), nullable=True)   # NULL = org-wide

    rating_label = Column(String(100), nullable=False)        # "Outstanding", "Exceeds Expectations"
    target_percentage = Column(Numeric(5, 2), nullable=False) # 10%
    target_count = Column(Integer, nullable=True)
    actual_count = Column(Integer, nullable=True)
    actual_percentage = Column(Numeric(5, 2), nullable=True)

    # Deviation
    variance = Column(Numeric(5, 2), nullable=True)
    is_within_target = Column(Boolean, nullable=True)

    computed_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    appraisal_cycle = relationship("AppraisalCycle")
    department = relationship("Department")

    __table_args__ = (
        Index("idx_bell_curve_cycle_dept", "appraisal_cycle_id", "department_id"),
    )


# ============================================================
# 4. 360-DEGREE FEEDBACK
# ============================================================

class FeedbackQuestion(Base):
    """Question bank for 360-degree feedback forms."""
    __tablename__ = "feedback_questions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    uuid = Column(GUID(), default=uuid.uuid4, unique=True, nullable=False)
    organization_id = Column(Integer, ForeignKey("organization.id"), nullable=False, index=True)

    question_text = Column(Text, nullable=False)
    question_type = Column(Enum(QuestionType), nullable=False)
    provider_type = Column(Enum(FeedbackProviderType), nullable=True)  # NULL = all types

    is_active = Column(Boolean, default=True)
    is_anonymous_allowed = Column(Boolean, default=True)
    competency_id = Column(Integer, ForeignKey("competency_frameworks.id"), nullable=True)
    rating_scale_id = Column(Integer, ForeignKey("rating_scales.id"), nullable=True)
    choices = Column(JSON, default=list)

    tags = Column(JSON, default=list)                         # ["leadership", "communication"]

    created_by = Column(Integer, ForeignKey("employees.id"), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    organization = relationship("Organization")
    competency = relationship("CompetencyFramework")
    rating_scale = relationship("RatingScale")
    creator = relationship("Employee", foreign_keys=[created_by])

    __table_args__ = (
        Index("idx_feedback_question_org", "organization_id", "is_active"),
    )


class FeedbackRequest(Base):
    """360-degree feedback request issued per appraisal cycle for an employee."""
    __tablename__ = "feedback_requests"

    id = Column(Integer, primary_key=True, autoincrement=True)
    uuid = Column(GUID(), default=uuid.uuid4, unique=True, nullable=False)
    appraisal_cycle_id = Column(Integer, ForeignKey("appraisal_cycles.id"), nullable=False, index=True)
    appraisal_record_id = Column(Integer, ForeignKey("appraisal_records.id"), nullable=True)
    employee_id = Column(Integer, ForeignKey("employees.id"), nullable=False, index=True)

    # Who nominated the reviewers
    initiated_by = Column(String(20), nullable=False)         # "employee", "manager", "hr"

    # Deadline
    due_date = Column(Date, nullable=False)
    status = Column(Enum(FeedbackRequestStatus), default=FeedbackRequestStatus.PENDING)

    # Minimum required responses
    min_peer_responses = Column(SmallInteger, default=3)
    min_subordinate_responses = Column(SmallInteger, default=2)

    # Summary (computed after collection)
    avg_rating = Column(Numeric(5, 2), nullable=True)
    response_summary = Column(JSON, nullable=True)            # Per-competency averages

    is_anonymous = Column(Boolean, default=True)

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    appraisal_cycle = relationship("AppraisalCycle")
    appraisal_record = relationship("AppraisalRecord")
    employee = relationship("Employee")

    __table_args__ = (
        UniqueConstraint("appraisal_cycle_id", "employee_id", name="uq_feedback_request_cycle"),
        Index("idx_feedback_request_employee", "employee_id", "status"),
    )


class FeedbackProvider(Base):
    """Nominated reviewers for a 360 feedback request."""
    __tablename__ = "feedback_providers"

    id = Column(Integer, primary_key=True, autoincrement=True)
    uuid = Column(GUID(), default=uuid.uuid4, unique=True, nullable=False)
    feedback_request_id = Column(Integer, ForeignKey("feedback_requests.id"), nullable=False, index=True)
    provider_id = Column(Integer, ForeignKey("employees.id"), nullable=False)

    provider_type = Column(Enum(FeedbackProviderType), nullable=False)

    # Approval of nomination
    approved_by_manager = Column(Boolean, nullable=True)      # NULL = pending
    approved_at = Column(DateTime, nullable=True)
    rejection_reason = Column(String(255), nullable=True)

    # Invite tracking
    invite_sent_at = Column(DateTime, nullable=True)
    reminder_sent_count = Column(SmallInteger, default=0)
    last_reminder_sent_at = Column(DateTime, nullable=True)

    # Completion
    status = Column(Enum(FeedbackRequestStatus), default=FeedbackRequestStatus.PENDING)
    completed_at = Column(DateTime, nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    feedback_request = relationship("FeedbackRequest")
    provider = relationship("Employee")

    __table_args__ = (
        UniqueConstraint("feedback_request_id", "provider_id", name="uq_feedback_provider"),
        Index("idx_feedback_provider_provider", "provider_id", "status"),
    )


class FeedbackResponse(Base):
    """Feedback submitted by a 360-degree reviewer."""
    __tablename__ = "feedback_responses"

    id = Column(Integer, primary_key=True, autoincrement=True)
    uuid = Column(GUID(), default=uuid.uuid4, unique=True, nullable=False)
    feedback_provider_id = Column(Integer, ForeignKey("feedback_providers.id"), nullable=False, index=True)
    feedback_request_id = Column(Integer, ForeignKey("feedback_requests.id"), nullable=False)

    # Per-question answers stored as JSON array for flexibility
    # [{"question_id": 1, "rating": 4, "text": "Great communicator", "competency_id": 3}]
    answers = Column(JSON, nullable=False, default=list)

    # Narrative
    overall_comments = Column(Text, nullable=True)
    strengths_observed = Column(Text, nullable=True)
    development_suggestions = Column(Text, nullable=True)

    overall_rating = Column(Numeric(5, 2), nullable=True)

    is_submitted = Column(Boolean, default=False)
    submitted_at = Column(DateTime, nullable=True)

    # Anonymization token
    anon_token = Column(String(64), nullable=True, unique=True)

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    feedback_provider = relationship("FeedbackProvider")
    feedback_request = relationship("FeedbackRequest")

    __table_args__ = (
        Index("idx_feedback_response_request", "feedback_request_id"),
    )


# ============================================================
# 5. COMPETENCY & SKILLS
# ============================================================

class CompetencyFramework(Base):
    """Library of competencies / behaviors expected in the organization."""
    __tablename__ = "competency_frameworks"

    id = Column(Integer, primary_key=True, autoincrement=True)
    uuid = Column(GUID(), default=uuid.uuid4, unique=True, nullable=False)
    organization_id = Column(Integer, ForeignKey("organization.id"), nullable=False, index=True)

    name = Column(String(150), nullable=False)                # "Communication", "Leadership"
    description = Column(Text, nullable=True)
    category = Column(String(100), nullable=True)             # "Core", "Leadership", "Technical"
    is_active = Column(Boolean, default=True)
    is_core = Column(Boolean, default=False)                  # Applies to all roles

    # Proficiency levels as JSON
    # [{"level": 1, "label": "Novice", "description": "..."},  {"level": 5, "label": "Expert", ...}]
    proficiency_levels = Column(JSON, nullable=False, default=list)

    # Behavioral indicators per level
    behavioral_indicators = Column(JSON, nullable=True)

    tags = Column(JSON, default=list)

    created_by = Column(Integer, ForeignKey("employees.id"), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    organization = relationship("Organization")
    creator = relationship("Employee", foreign_keys=[created_by])

    __table_args__ = (
        UniqueConstraint("organization_id", "name", name="uq_competency_name"),
        Index("idx_competency_org_active", "organization_id", "is_active"),
    )


class CompetencyMapping(Base):
    """Maps competencies to job roles, departments, or grades."""
    __tablename__ = "competency_mappings"

    id = Column(Integer, primary_key=True, autoincrement=True)
    organization_id = Column(Integer, ForeignKey("organization.id"), nullable=False)
    competency_id = Column(Integer, ForeignKey("competency_frameworks.id"), nullable=False, index=True)

    # Target (at least one must be set)
    role_id = Column(Integer, ForeignKey("job_titles.id"), nullable=True)
    department_id = Column(Integer, ForeignKey("departments.id"), nullable=True)
    grade_id = Column(Integer, nullable=True)

    required_proficiency_level = Column(SmallInteger, nullable=False)
    weight = Column(Numeric(5, 2), default=100.00)
    is_mandatory = Column(Boolean, default=True)

    created_by = Column(Integer, ForeignKey("employees.id"), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    organization = relationship("Organization")
    competency = relationship("CompetencyFramework")
    role = relationship("JobTitle", foreign_keys=[role_id])
    department = relationship("Department")
    creator = relationship("Employee", foreign_keys=[created_by])

    __table_args__ = (
        Index("idx_competency_mapping_role", "role_id", "competency_id"),
        Index("idx_competency_mapping_dept", "department_id", "competency_id"),
    )


class EmployeeCompetency(Base):
    """Rated competency scores for an employee per appraisal cycle."""
    __tablename__ = "employee_competencies"

    id = Column(Integer, primary_key=True, autoincrement=True)
    uuid = Column(GUID(), default=uuid.uuid4, unique=True, nullable=False)
    employee_id = Column(Integer, ForeignKey("employees.id"), nullable=False, index=True)
    competency_id = Column(Integer, ForeignKey("competency_frameworks.id"), nullable=False)
    appraisal_cycle_id = Column(Integer, ForeignKey("appraisal_cycles.id"), nullable=True)
    appraisal_record_id = Column(Integer, ForeignKey("appraisal_records.id"), nullable=True)

    # Ratings
    self_rating = Column(SmallInteger, nullable=True)
    manager_rating = Column(SmallInteger, nullable=True)
    final_rating = Column(SmallInteger, nullable=True)
    feedback_360_rating = Column(Numeric(5, 2), nullable=True)

    # Required vs actual
    required_level = Column(SmallInteger, nullable=True)
    gap = Column(SmallInteger, nullable=True)                 # required - final_rating

    self_comments = Column(Text, nullable=True)
    manager_comments = Column(Text, nullable=True)

    assessed_date = Column(Date, nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    employee = relationship("Employee", foreign_keys=[employee_id])
    competency = relationship("CompetencyFramework")
    appraisal_cycle = relationship("AppraisalCycle")
    appraisal_record = relationship("AppraisalRecord")

    __table_args__ = (
        UniqueConstraint("employee_id", "competency_id", "appraisal_cycle_id",
                         name="uq_employee_competency_cycle"),
        Index("idx_emp_competency_cycle", "appraisal_cycle_id", "employee_id"),
    )


class SkillsGapAnalysis(Base):
    """Skills gap analysis report per employee."""
    __tablename__ = "skills_gap_analyses"

    id = Column(Integer, primary_key=True, autoincrement=True)
    uuid = Column(GUID(), default=uuid.uuid4, unique=True, nullable=False)
    employee_id = Column(Integer, ForeignKey("employees.id"), nullable=False, index=True)
    appraisal_cycle_id = Column(Integer, ForeignKey("appraisal_cycles.id"), nullable=True)
    conducted_by = Column(Integer, ForeignKey("employees.id"), nullable=False)

    analysis_date = Column(Date, nullable=False, default=date.today)

    # Gap summary per competency stored as JSON
    # [{"competency_id": 1, "name": "Leadership", "required": 4, "actual": 2, "gap": 2,
    #   "priority": "high", "recommended_actions": ["training", "mentoring"]}]
    gap_details = Column(JSON, nullable=False, default=list)

    # Overall
    overall_readiness_score = Column(Numeric(5, 2), nullable=True)  # 0-100%
    critical_gaps_count = Column(SmallInteger, default=0)

    # Training recommendations
    recommended_training = Column(JSON, default=list)         # [{"course": "...", "provider": "..."}]
    development_priority = Column(String(20), default="MEDIUM")  # LOW, MEDIUM, HIGH, CRITICAL

    notes = Column(Text, nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    employee = relationship("Employee", foreign_keys=[employee_id])
    appraisal_cycle = relationship("AppraisalCycle")
    assessor = relationship("Employee", foreign_keys=[conducted_by])

    __table_args__ = (
        Index("idx_skills_gap_employee_cycle", "employee_id", "appraisal_cycle_id"),
    )


# ============================================================
# 6. CONTINUOUS FEEDBACK & 1-ON-1
# ============================================================

class ContinuousFeedback(Base):
    """Anytime / real-time feedback given between employees outside formal cycles."""
    __tablename__ = "continuous_feedback"

    id = Column(Integer, primary_key=True, autoincrement=True)
    uuid = Column(GUID(), default=uuid.uuid4, unique=True, nullable=False)
    organization_id = Column(Integer, ForeignKey("organization.id"), nullable=False)

    giver_id = Column(Integer, ForeignKey("employees.id"), nullable=False, index=True)
    receiver_id = Column(Integer, ForeignKey("employees.id"), nullable=False, index=True)

    feedback_type = Column(String(30), nullable=False)        # "praise", "constructive", "suggestion"
    feedback_text = Column(Text, nullable=False)

    # Competency linkage
    competency_id = Column(Integer, ForeignKey("competency_frameworks.id"), nullable=True)
    goal_id = Column(Integer, ForeignKey("employee_goals.id"), nullable=True)

    is_anonymous = Column(Boolean, default=False)
    is_visible_to_manager = Column(Boolean, default=True)
    is_shared_with_hr = Column(Boolean, default=False)

    # Reaction
    receiver_acknowledged = Column(Boolean, default=False)
    receiver_acknowledged_at = Column(DateTime, nullable=True)
    receiver_reaction = Column(String(20), nullable=True)     # "helpful", "not_relevant"

    tags = Column(JSON, default=list)

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    organization = relationship("Organization")
    giver = relationship("Employee", foreign_keys=[giver_id])
    receiver = relationship("Employee", foreign_keys=[receiver_id])
    competency = relationship("CompetencyFramework")
    goal = relationship("EmployeeGoal")

    __table_args__ = (
        Index("idx_continuous_feedback_receiver", "receiver_id", "created_at"),
        Index("idx_continuous_feedback_giver", "giver_id"),
    )


class OneOnOneMeeting(Base):
    """Scheduled 1-on-1 meetings between manager and employee."""
    __tablename__ = "one_on_one_meetings"

    id = Column(Integer, primary_key=True, autoincrement=True)
    uuid = Column(GUID(), default=uuid.uuid4, unique=True, nullable=False)
    organization_id = Column(Integer, ForeignKey("organization.id"), nullable=False)
    manager_id = Column(Integer, ForeignKey("employees.id"), nullable=False, index=True)
    employee_id = Column(Integer, ForeignKey("employees.id"), nullable=False, index=True)

    # Schedule
    scheduled_date = Column(DateTime, nullable=False)
    duration_minutes = Column(SmallInteger, default=30)
    location = Column(String(255), nullable=True)             # Room / Video link
    meeting_type = Column(String(30), default="REGULAR")      # REGULAR, CHECK_IN, PERFORMANCE, CAREER

    # Recurrence
    is_recurring = Column(Boolean, default=False)
    recurrence_pattern = Column(String(50), nullable=True)    # "WEEKLY", "BIWEEKLY", "MONTHLY"
    recurrence_end_date = Column(Date, nullable=True)
    series_id = Column(GUID(), nullable=True)   # Groups recurring meetings

    # Content
    pre_meeting_notes = Column(Text, nullable=True)
    meeting_notes = Column(Text, nullable=True)
    key_decisions = Column(Text, nullable=True)

    # Status
    status = Column(String(30), default="SCHEDULED")          # SCHEDULED, COMPLETED, CANCELLED, RESCHEDULED
    completed_at = Column(DateTime, nullable=True)
    cancelled_reason = Column(String(255), nullable=True)

    # Appraisal linkage
    appraisal_cycle_id = Column(Integer, ForeignKey("appraisal_cycles.id"), nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    organization = relationship("Organization")
    manager = relationship("Employee", foreign_keys=[manager_id])
    employee = relationship("Employee", foreign_keys=[employee_id])
    appraisal_cycle = relationship("AppraisalCycle")

    __table_args__ = (
        Index("idx_one_on_one_manager_emp", "manager_id", "employee_id", "scheduled_date"),
    )


class OneOnOneAgendaItem(Base):
    """Agenda topics and action items for a 1-on-1 meeting."""
    __tablename__ = "one_on_one_agenda_items"

    id = Column(Integer, primary_key=True, autoincrement=True)
    meeting_id = Column(Integer, ForeignKey("one_on_one_meetings.id"), nullable=False, index=True)

    item_type = Column(String(30), nullable=False)            # "agenda", "action_item", "follow_up"
    title = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    added_by = Column(Integer, ForeignKey("employees.id"), nullable=False)
    item_order = Column(SmallInteger, default=0)

    # Action item fields
    assigned_to = Column(Integer, ForeignKey("employees.id"), nullable=True)
    due_date = Column(Date, nullable=True)
    is_completed = Column(Boolean, default=False)
    completed_at = Column(DateTime, nullable=True)
    completion_notes = Column(Text, nullable=True)

    # Carry-forward from previous meeting
    carried_from_meeting_id = Column(Integer, ForeignKey("one_on_one_meetings.id"), nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    meeting = relationship("OneOnOneMeeting", foreign_keys=[meeting_id])
    added_by_employee = relationship("Employee", foreign_keys=[added_by])
    assigned_to_employee = relationship("Employee", foreign_keys=[assigned_to])
    carried_from_meeting = relationship("OneOnOneMeeting", foreign_keys=[carried_from_meeting_id])

    __table_args__ = (
        Index("idx_agenda_item_meeting", "meeting_id", "item_type"),
    )


class PerformanceNote(Base):
    """Manager notes / informal observations about employee performance."""
    __tablename__ = "performance_notes"

    id = Column(Integer, primary_key=True, autoincrement=True)
    uuid = Column(GUID(), default=uuid.uuid4, unique=True, nullable=False)
    manager_id = Column(Integer, ForeignKey("employees.id"), nullable=False, index=True)
    employee_id = Column(Integer, ForeignKey("employees.id"), nullable=False, index=True)

    note_type = Column(String(30), nullable=False)            # "observation", "incident", "commendation"
    note_date = Column(Date, nullable=False, default=date.today)
    title = Column(String(255), nullable=False)
    content = Column(Text, nullable=False)

    is_private = Column(Boolean, default=False)               # Private to manager only
    is_shared_with_employee = Column(Boolean, default=False)

    # Linkage
    goal_id = Column(Integer, ForeignKey("employee_goals.id"), nullable=True)
    competency_id = Column(Integer, ForeignKey("competency_frameworks.id"), nullable=True)
    one_on_one_id = Column(Integer, ForeignKey("one_on_one_meetings.id"), nullable=True)

    attachments = Column(JSON, default=list)
    tags = Column(JSON, default=list)

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    manager = relationship("Employee", foreign_keys=[manager_id])
    employee = relationship("Employee", foreign_keys=[employee_id])
    goal = relationship("EmployeeGoal")
    competency = relationship("CompetencyFramework")
    one_on_one = relationship("OneOnOneMeeting")

    __table_args__ = (
        Index("idx_perf_note_emp_date", "employee_id", "note_date"),
        Index("idx_perf_note_manager", "manager_id", "note_date"),
    )


# ============================================================
# 7. PERFORMANCE IMPROVEMENT PLAN (PIP)
# ============================================================

class PIIPlan(Base):
    """Performance Improvement Plan master record."""
    __tablename__ = "pii_plans"

    id = Column(Integer, primary_key=True, autoincrement=True)
    uuid = Column(GUID(), default=uuid.uuid4, unique=True, nullable=False)
    organization_id = Column(Integer, ForeignKey("organization.id"), nullable=False)
    employee_id = Column(Integer, ForeignKey("employees.id"), nullable=False, index=True)
    manager_id = Column(Integer, ForeignKey("employees.id"), nullable=False)
    hr_owner_id = Column(Integer, ForeignKey("employees.id"), nullable=True)

    # Linked appraisal
    appraisal_record_id = Column(Integer, ForeignKey("appraisal_records.id"), nullable=True)

    title = Column(String(255), nullable=False)
    reason = Column(Text, nullable=False)                     # Why PIP was initiated

    # Duration
    start_date = Column(Date, nullable=False)
    end_date = Column(Date, nullable=False)
    review_frequency = Column(String(30), default="WEEKLY")   # WEEKLY, BIWEEKLY, MONTHLY

    status = Column(Enum(PIPStatus), default=PIPStatus.DRAFT)

    # Outcome
    outcome_notes = Column(Text, nullable=True)
    closed_at = Column(DateTime, nullable=True)
    closed_by = Column(Integer, ForeignKey("employees.id"), nullable=True)

    # Employee acknowledgment
    employee_acknowledged = Column(Boolean, default=False)
    employee_acknowledged_at = Column(DateTime, nullable=True)
    employee_comments = Column(Text, nullable=True)

    # HR approval
    hr_approved = Column(Boolean, default=False)
    hr_approved_at = Column(DateTime, nullable=True)
    hr_approval_notes = Column(Text, nullable=True)

    support_resources = Column(Text, nullable=True)           # Training, coaching offered
    attachments = Column(JSON, default=list)

    created_by = Column(Integer, ForeignKey("employees.id"), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    organization = relationship("Organization")
    employee = relationship("Employee", foreign_keys=[employee_id])
    manager = relationship("Employee", foreign_keys=[manager_id])
    hr_owner = relationship("Employee", foreign_keys=[hr_owner_id])
    appraisal_record = relationship("AppraisalRecord")
    closed_by_employee = relationship("Employee", foreign_keys=[closed_by])
    creator = relationship("Employee", foreign_keys=[created_by])

    __table_args__ = (
        Index("idx_pip_employee_status", "employee_id", "status"),
    )


class PIIObjective(Base):
    """Specific, measurable objectives within a PIP."""
    __tablename__ = "pii_objectives"

    id = Column(Integer, primary_key=True, autoincrement=True)
    uuid = Column(GUID(), default=uuid.uuid4, unique=True, nullable=False)
    pip_plan_id = Column(Integer, ForeignKey("pii_plans.id"), nullable=False, index=True)

    title = Column(String(255), nullable=False)
    description = Column(Text, nullable=False)
    success_criteria = Column(Text, nullable=False)

    measurement_type = Column(Enum(GoalMeasurementType), nullable=False)
    target_value = Column(Numeric(15, 2), nullable=True)
    current_value = Column(Numeric(15, 2), default=0)
    unit = Column(String(50), nullable=True)

    due_date = Column(Date, nullable=False)
    priority = Column(String(20), default="HIGH")

    status = Column(Enum(GoalStatus), default=GoalStatus.ACTIVE)
    achievement_percentage = Column(Numeric(5, 2), nullable=True)
    outcome_notes = Column(Text, nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    pip_plan = relationship("PIIPlan")

    __table_args__ = (
        Index("idx_pip_objective_plan", "pip_plan_id", "status"),
    )


class PIIProgressLog(Base):
    """Periodic progress check-in entries for an active PIP."""
    __tablename__ = "pii_progress_logs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    uuid = Column(GUID(), default=uuid.uuid4, unique=True, nullable=False)
    pip_plan_id = Column(Integer, ForeignKey("pii_plans.id"), nullable=False, index=True)
    logged_by = Column(Integer, ForeignKey("employees.id"), nullable=False)

    log_date = Column(Date, nullable=False, default=date.today)

    # Per-objective progress
    objective_updates = Column(JSON, nullable=False, default=list)
    # [{"objective_id": 1, "current_value": 80, "progress": 80, "status": "ON_TRACK", "notes": "..."}]

    overall_status = Column(Enum(PIPStatus), nullable=False)
    observations = Column(Text, nullable=True)
    manager_recommendations = Column(Text, nullable=True)
    support_given = Column(Text, nullable=True)

    # Employee response
    employee_response = Column(Text, nullable=True)
    employee_responded_at = Column(DateTime, nullable=True)

    next_review_date = Column(Date, nullable=True)
    meeting_held = Column(Boolean, default=True)
    meeting_notes = Column(Text, nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    pip_plan = relationship("PIIPlan")
    logger = relationship("Employee", foreign_keys=[logged_by])

    __table_args__ = (
        Index("idx_pip_progress_plan_date", "pip_plan_id", "log_date"),
    )


# ============================================================
# 8. SUCCESSION PLANNING & TALENT REVIEW
# ============================================================

class TalentReview(Base):
    """Talent review session (9-box, high-potential identification)."""
    __tablename__ = "talent_reviews"

    id = Column(Integer, primary_key=True, autoincrement=True)
    uuid = Column(GUID(), default=uuid.uuid4, unique=True, nullable=False)
    organization_id = Column(Integer, ForeignKey("organization.id"), nullable=False, index=True)
    appraisal_cycle_id = Column(Integer, ForeignKey("appraisal_cycles.id"), nullable=True)

    name = Column(String(150), nullable=False)                # "H2 2025 Talent Review"
    review_date = Column(Date, nullable=False)
    facilitator_id = Column(Integer, ForeignKey("employees.id"), nullable=False)

    department_id = Column(Integer, ForeignKey("departments.id"), nullable=True)  # NULL = org-wide

    status = Column(String(30), default="DRAFT")              # DRAFT, IN_PROGRESS, COMPLETED, ARCHIVED
    notes = Column(Text, nullable=True)
    session_minutes = Column(Text, nullable=True)

    created_by = Column(Integer, ForeignKey("employees.id"), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    organization = relationship("Organization")
    appraisal_cycle = relationship("AppraisalCycle")
    facilitator = relationship("Employee", foreign_keys=[facilitator_id])
    department = relationship("Department")
    creator = relationship("Employee", foreign_keys=[created_by])

    __table_args__ = (
        Index("idx_talent_review_org_cycle", "organization_id", "appraisal_cycle_id"),
    )


class TalentReviewParticipant(Base):
    """Employees evaluated in a talent review session."""
    __tablename__ = "talent_review_participants"

    id = Column(Integer, primary_key=True, autoincrement=True)
    talent_review_id = Column(Integer, ForeignKey("talent_reviews.id"), nullable=False, index=True)
    employee_id = Column(Integer, ForeignKey("employees.id"), nullable=False, index=True)

    # 9-Box Assessment
    performance_rating = Column(SmallInteger, nullable=True)  # 1=Low, 2=Med, 3=High
    potential_rating = Column(SmallInteger, nullable=True)    # 1=Low, 2=Med, 3=High
    nine_box_position = Column(Enum(NineBoxPosition), nullable=True)
    talent_category = Column(Enum(TalentCategory), nullable=True)

    # Flight risk
    flight_risk = Column(String(20), nullable=True)           # LOW, MEDIUM, HIGH
    flight_risk_reason = Column(Text, nullable=True)

    # Development
    readiness_for_promotion = Column(String(20), nullable=True)  # "READY_NOW", "READY_1_2_YR", "NOT_READY"
    development_needs = Column(Text, nullable=True)
    retention_priority = Column(String(20), nullable=True)    # LOW, MEDIUM, HIGH, CRITICAL

    reviewer_comments = Column(Text, nullable=True)
    is_key_talent = Column(Boolean, default=False)
    is_succession_candidate = Column(Boolean, default=False)

    reviewed_by = Column(Integer, ForeignKey("employees.id"), nullable=False)
    reviewed_at = Column(DateTime, nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    talent_review = relationship("TalentReview")
    employee = relationship("Employee", foreign_keys=[employee_id])
    reviewer = relationship("Employee", foreign_keys=[reviewed_by])

    __table_args__ = (
        UniqueConstraint("talent_review_id", "employee_id", name="uq_talent_review_participant"),
    )


class SuccessionPlan(Base):
    """Succession plan for a critical organizational position/role."""
    __tablename__ = "succession_plans"

    id = Column(Integer, primary_key=True, autoincrement=True)
    uuid = Column(GUID(), default=uuid.uuid4, unique=True, nullable=False)
    organization_id = Column(Integer, ForeignKey("organization.id"), nullable=False, index=True)

    # The role/position being planned for
    position_title = Column(String(255), nullable=False)
    department_id = Column(Integer, ForeignKey("departments.id"), nullable=True)
    role_id = Column(Integer, ForeignKey("job_titles.id"), nullable=True)

    # Current incumbent
    incumbent_employee_id = Column(Integer, ForeignKey("employees.id"), nullable=True)
    position_criticality = Column(String(20), default="HIGH")  # LOW, MEDIUM, HIGH, CRITICAL

    plan_owner_id = Column(Integer, ForeignKey("employees.id"), nullable=False)
    role_id = Column(Integer, ForeignKey("job_titles.id"), nullable=True) # Overridden/corrected
    review_frequency = Column(String(30), default="ANNUAL")

    is_active = Column(Boolean, default=True)
    notes = Column(Text, nullable=True)

    created_by = Column(Integer, ForeignKey("employees.id"), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    organization = relationship("Organization")
    department = relationship("Department")
    role = relationship("JobTitle", foreign_keys=[role_id])
    incumbent = relationship("Employee", foreign_keys=[incumbent_employee_id])
    plan_owner = relationship("Employee", foreign_keys=[plan_owner_id])
    creator = relationship("Employee", foreign_keys=[created_by])

    __table_args__ = (
        Index("idx_succession_plan_dept", "department_id", "is_active"),
    )


class SuccessionCandidate(Base):
    """Employees identified as succession candidates for a critical role."""
    __tablename__ = "succession_candidates"

    id = Column(Integer, primary_key=True, autoincrement=True)
    uuid = Column(GUID(), default=uuid.uuid4, unique=True, nullable=False)
    succession_plan_id = Column(Integer, ForeignKey("succession_plans.id"), nullable=False, index=True)
    employee_id = Column(Integer, ForeignKey("employees.id"), nullable=False, index=True)

    readiness = Column(String(30), nullable=False)            # "READY_NOW", "READY_1_YR", "READY_3_YR"
    readiness_score = Column(Numeric(5, 2), nullable=True)    # 0-100

    # Competency gaps
    gap_assessment = Column(JSON, nullable=True)              # Per-competency gap summary
    development_plan = Column(Text, nullable=True)

    # Tracking
    is_primary_candidate = Column(Boolean, default=False)
    priority_rank = Column(SmallInteger, nullable=True)       # 1 = top candidate

    retention_risk = Column(String(20), nullable=True)
    notes = Column(Text, nullable=True)
    last_reviewed_at = Column(DateTime, nullable=True)
    reviewed_by = Column(Integer, ForeignKey("employees.id"), nullable=True)

    is_active = Column(Boolean, default=True)

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    succession_plan = relationship("SuccessionPlan")
    employee = relationship("Employee", foreign_keys=[employee_id])
    reviewer = relationship("Employee", foreign_keys=[reviewed_by])

    __table_args__ = (
        UniqueConstraint("succession_plan_id", "employee_id", name="uq_succession_candidate"),
        Index("idx_succession_candidate_plan", "succession_plan_id", "readiness"),
    )


# ============================================================
# 9. ANALYTICS, NOTIFICATIONS & COMPENSATION INTEGRATION
# ============================================================

class PerformanceMetrics(Base):
    """Pre-computed analytics/KPI store for trend dashboards."""
    __tablename__ = "performance_metrics"

    id = Column(Integer, primary_key=True, autoincrement=True)
    organization_id = Column(Integer, ForeignKey("organization.id"), nullable=False)
    department_id = Column(Integer, ForeignKey("departments.id"), nullable=True)
    appraisal_cycle_id = Column(Integer, ForeignKey("appraisal_cycles.id"), nullable=True)

    metric_type = Column(String(100), nullable=False)         # "avg_performance_score", "goal_completion_rate"
    metric_scope = Column(String(30), nullable=False)         # "organization", "department", "team"
    scope_id = Column(Integer, nullable=True)                 # dept/team ID

    value = Column(Numeric(10, 4), nullable=False)
    previous_value = Column(Numeric(10, 4), nullable=True)
    change_percentage = Column(Numeric(8, 4), nullable=True)

    breakdown = Column(JSON, nullable=True)                   # Detailed sub-breakdowns
    period_label = Column(String(50), nullable=True)          # "Q4 2025", "FY 2025"
    computed_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    organization = relationship("Organization")
    department = relationship("Department")
    appraisal_cycle = relationship("AppraisalCycle")

    __table_args__ = (
        Index("idx_perf_metrics_org_cycle", "organization_id", "appraisal_cycle_id", "metric_type"),
        Index("idx_perf_metrics_scope", "metric_scope", "scope_id"),
    )


class NotificationTemplate(Base):
    """Reusable email/in-app notification templates for appraisal reminders."""
    __tablename__ = "notification_templates"

    id = Column(Integer, primary_key=True, autoincrement=True)
    uuid = Column(GUID(), default=uuid.uuid4, unique=True, nullable=False)
    organization_id = Column(Integer, ForeignKey("organization.id"), nullable=False, index=True)

    name = Column(String(150), nullable=False)
    notification_type = Column(Enum(NotificationType), nullable=False)
    channel = Column(String(20), nullable=False)              # "EMAIL", "IN_APP", "SMS"

    subject = Column(String(255), nullable=True)              # For email
    body_template = Column(Text, nullable=False)              # Supports {{employee_name}}, {{due_date}} etc.

    is_active = Column(Boolean, default=True)
    is_default = Column(Boolean, default=False)

    created_by = Column(Integer, ForeignKey("employees.id"), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    organization = relationship("Organization")
    creator = relationship("Employee", foreign_keys=[created_by])

    __table_args__ = (
        UniqueConstraint("organization_id", "name", name="uq_notif_template_name"),
    )


class PerformanceNotification(Base):
    """Log of sent notifications for appraisal cycle milestones."""
    __tablename__ = "performance_notifications"

    id = Column(Integer, primary_key=True, autoincrement=True)
    uuid = Column(GUID(), default=uuid.uuid4, unique=True, nullable=False)
    organization_id = Column(Integer, ForeignKey("organization.id"), nullable=False)
    appraisal_cycle_id = Column(Integer, ForeignKey("appraisal_cycles.id"), nullable=True)

    notification_type = Column(Enum(NotificationType), nullable=False)
    template_id = Column(Integer, ForeignKey("notification_templates.id"), nullable=True)
    channel = Column(String(20), nullable=False)

    recipient_id = Column(Integer, ForeignKey("employees.id"), nullable=False, index=True)
    sent_at = Column(DateTime, nullable=True)
    scheduled_at = Column(DateTime, nullable=True)

    is_sent = Column(Boolean, default=False)
    is_read = Column(Boolean, default=False)
    read_at = Column(DateTime, nullable=True)

    # Rendered content
    subject = Column(String(255), nullable=True)
    body = Column(Text, nullable=True)

    # Delivery tracking
    delivery_status = Column(String(30), nullable=True)       # "delivered", "bounced", "failed"
    failure_reason = Column(String(255), nullable=True)
    retry_count = Column(SmallInteger, default=0)

    # Context reference
    reference_type = Column(String(50), nullable=True)        # "appraisal_record", "goal", "pip"
    reference_id = Column(Integer, nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    organization = relationship("Organization")
    appraisal_cycle = relationship("AppraisalCycle")
    template = relationship("NotificationTemplate")
    recipient = relationship("Employee", foreign_keys=[recipient_id])

    __table_args__ = (
        Index("idx_perf_notif_recipient", "recipient_id", "is_sent", "notification_type"),
        Index("idx_perf_notif_cycle", "appraisal_cycle_id", "notification_type"),
    )


class CompensationIntegration(Base):
    """Bridges performance appraisal outcomes to compensation & promotion workflows."""
    __tablename__ = "compensation_integrations"

    id = Column(Integer, primary_key=True, autoincrement=True)
    uuid = Column(GUID(), default=uuid.uuid4, unique=True, nullable=False)
    appraisal_record_id = Column(Integer, ForeignKey("appraisal_records.id"), nullable=False, unique=True)
    employee_id = Column(Integer, ForeignKey("employees.id"), nullable=False, index=True)
    appraisal_cycle_id = Column(Integer, ForeignKey("appraisal_cycles.id"), nullable=False)

    # Appraisal outcome
    final_rating_label = Column(String(100), nullable=True)
    final_score = Column(Numeric(5, 2), nullable=True)

    # Compensation recommendation
    merit_increase_recommended = Column(Boolean, default=False)
    merit_increase_percentage = Column(Numeric(5, 2), nullable=True)
    bonus_recommended = Column(Boolean, default=False)
    bonus_amount = Column(Numeric(12, 2), nullable=True)
    bonus_type = Column(String(50), nullable=True)            # "performance_bonus", "spot_award"

    # Promotion
    promotion_recommended = Column(Boolean, default=False)
    recommended_grade = Column(String(50), nullable=True)
    recommended_role_id = Column(Integer, ForeignKey("job_titles.id"), nullable=True)

    # Workflow status
    status = Column(String(30), default="PENDING")            # PENDING, SUBMITTED, APPROVED, REJECTED
    submitted_to_compensation_at = Column(DateTime, nullable=True)
    submitted_by = Column(Integer, ForeignKey("employees.id"), nullable=True)

    # Result from compensation module
    compensation_action_id = Column(Integer, nullable=True)   # FK to compensation module
    action_effective_date = Column(Date, nullable=True)
    action_notes = Column(Text, nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    appraisal_record = relationship("AppraisalRecord")
    employee = relationship("Employee", foreign_keys=[employee_id])
    appraisal_cycle = relationship("AppraisalCycle")
    recommended_role = relationship("JobTitle", foreign_keys=[recommended_role_id])
    submitted_by_employee = relationship("Employee", foreign_keys=[submitted_by])

    __table_args__ = (
        Index("idx_comp_integration_cycle", "appraisal_cycle_id", "status"),
    )


# ============================================================
# ADDITIONAL PERFORMANCE INDEXES
# ============================================================

# Cross-table reporting indexes
Index("idx_appraisal_record_emp_cycle_status",
      AppraisalRecord.employee_id,
      AppraisalRecord.appraisal_cycle_id,
      AppraisalRecord.status)

Index("idx_emp_goal_emp_end_status",
      EmployeeGoal.employee_id,
      EmployeeGoal.end_date,
      EmployeeGoal.status)

Index("idx_pip_plan_manager",
      PIIPlan.manager_id,
      PIIPlan.status)

Index("idx_talent_review_participant_nine_box",
      TalentReviewParticipant.talent_review_id,
      TalentReviewParticipant.nine_box_position)
