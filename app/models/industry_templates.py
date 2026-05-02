import uuid
from datetime import datetime
from sqlalchemy import Column, String, Boolean, DateTime, Enum, Integer, ForeignKey, Text, Time, Numeric, JSON, Date
from sqlalchemy.orm import relationship
import enum
from app.db.base_class import Base
from app.models.organization import GUID

# ============================================================================
# ENUMS
# ============================================================================

class QuickSetupStatus(str, enum.Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"

# ============================================================================
# TEMPLATE MODELS
# ============================================================================

class IndustryDepartmentTemplate(Base):
    __tablename__ = "industry_department_templates"
    
    id = Column(Integer, primary_key=True, index=True)
    industry_id = Column(Integer, ForeignKey('industries.id'), nullable=False)
    
    department_code = Column(String(50), nullable=False)
    department_name = Column(String(150), nullable=False)
    description = Column(Text, nullable=True)
    
    industry = relationship("Industry")

class IndustryJobTitleTemplate(Base):
    __tablename__ = "industry_job_title_templates"
    
    id = Column(Integer, primary_key=True, index=True)
    industry_id = Column(Integer, ForeignKey('industries.id'), nullable=False)
    
    title_code = Column(String(50), nullable=False)
    title_name = Column(String(150), nullable=False)
    job_level = Column(String(50), nullable=True)
    job_family = Column(String(100), nullable=True)
    description = Column(Text, nullable=True)
    responsibilities = Column(Text, nullable=True)
    qualifications = Column(Text, nullable=True)
    
    industry = relationship("Industry")

class IndustryRoleTemplate(Base):
    __tablename__ = "industry_role_templates"
    
    id = Column(Integer, primary_key=True, index=True)
    industry_id = Column(Integer, ForeignKey('industries.id'), nullable=False)
    
    role_code = Column(String(100), nullable=False)
    role_name = Column(String(150), nullable=False)
    role_description = Column(Text, nullable=True)
    role_level = Column(Integer, default=0)
    scope = Column(String(50), default='organization')
    color_code = Column(String(20), nullable=True)
    icon = Column(String(50), nullable=True)
    
    # List of permission codes to assign
    permission_codes = Column(JSON, nullable=True) # e.g. ["1", "5", "9"]
    
    industry = relationship("Industry")

class IndustryShiftTemplate(Base):
    __tablename__ = "industry_shift_templates"
    
    id = Column(Integer, primary_key=True, index=True)
    industry_id = Column(Integer, ForeignKey('industries.id'), nullable=False)
    
    shift_code = Column(String(50), nullable=False)
    shift_name = Column(String(150), nullable=False)
    shift_type = Column(String(50), nullable=False) # 'fixed', 'rotating', etc.
    
    start_time = Column(Time, nullable=False)
    end_time = Column(Time, nullable=False)
    work_hours = Column(Numeric(4, 2), nullable=False)
    break_hours = Column(Numeric(4, 2), default=0)
    has_break = Column(Boolean, default=False)
    
    late_arrival_grace_minutes = Column(Integer, default=0)
    early_departure_grace_minutes = Column(Integer, default=0)
    week_off_days = Column(JSON, nullable=True)
    
    industry = relationship("Industry")

class IndustryAttendancePolicyTemplate(Base):
    __tablename__ = "industry_attendance_policy_templates"
    
    id = Column(Integer, primary_key=True, index=True)
    industry_id = Column(Integer, ForeignKey('industries.id'), nullable=False)
    
    policy_name = Column(String(150), nullable=False)
    working_days_per_week = Column(Integer, default=5)
    working_hours_per_day = Column(Numeric(4, 2), default=8.00)
    late_arrival_grace = Column(Integer, default=0)
    early_departure_grace = Column(Integer, default=0)
    overtime_enabled = Column(Boolean, default=True)
    regularization_allowed = Column(Boolean, default=True)
    
    industry = relationship("Industry")

class IndustryLeaveTypeTemplate(Base):
    __tablename__ = "industry_leave_type_templates"
    
    id = Column(Integer, primary_key=True, index=True)
    industry_id = Column(Integer, ForeignKey('industries.id'), nullable=False)
    
    leave_code = Column(String(50), nullable=False)
    leave_name = Column(String(150), nullable=False)
    description = Column(Text, nullable=True)
    accrual_type = Column(String(50), nullable=False) # 'monthly', 'yearly', etc.
    accrual_rate = Column(Numeric(5, 2), nullable=False)
    annual_quota = Column(Numeric(5, 2), nullable=False)
    max_balance = Column(Numeric(6, 2), nullable=True)
    color_code = Column(String(20), nullable=True)
    
    industry = relationship("Industry")

class IndustryLeavePolicyTemplate(Base):
    __tablename__ = "industry_leave_policy_templates"
    
    id = Column(Integer, primary_key=True, index=True)
    industry_id = Column(Integer, ForeignKey('industries.id'), nullable=False)
    
    policy_name = Column(String(150), nullable=False)
    description = Column(Text, nullable=True)
    
    # List of leave type codes to include in this policy
    leave_type_codes = Column(JSON, nullable=True) # e.g. ["CL", "SL", "PL"]
    
    industry = relationship("Industry")

class MasterCountryHoliday(Base):
    __tablename__ = "master_country_holidays"
    
    id = Column(Integer, primary_key=True, index=True)
    holiday_name = Column(String(200), nullable=False)
    holiday_date = Column(Date, nullable=False)
    holiday_type = Column(String(50), nullable=False) # 'public', 'restricted', etc.
    country = Column(String(100), nullable=False, index=True)

# ============================================================================
# JOB TRACKING
# ============================================================================

class QuickSetupJob(Base):
    __tablename__ = "quick_setup_jobs"
    
    id = Column(Integer, primary_key=True, index=True)
    uuid = Column(GUID(), default=uuid.uuid4, unique=True, nullable=False, index=True)
    organization_id = Column(Integer, ForeignKey('organization.id'), nullable=False, index=True)
    
    status = Column(Enum(QuickSetupStatus), default=QuickSetupStatus.PENDING, nullable=False)
    
    # Progress tracking
    progress_percentage = Column(Integer, default=0)
    logs = Column(JSON, nullable=True) # [{"step": "Departments", "status": "completed", "message": "5 departments created"}]
    
    # Store the user's selections for reference
    selections = Column(JSON, nullable=True)
    
    # Error logging
    error_log = Column(Text, nullable=True)
    
    started_at = Column(DateTime, default=datetime.utcnow)
    completed_at = Column(DateTime, nullable=True)
    
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    organization = relationship("Organization")
