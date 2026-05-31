from typing import Optional, Any
from sqlalchemy import (
    Column, Integer, String, Boolean, DateTime, Text, Enum, Date, Numeric, ForeignKey, Index, JSON
)
from sqlalchemy.orm import relationship
from datetime import datetime
import uuid
import enum
from app.db.base_class import Base
from app.models.organization import GUID

# ============================================================================
# ENUMS
# ============================================================================

class EmploymentType(str, enum.Enum):
    FULL_TIME = "full_time"
    PART_TIME = "part_time"
    CONTRACT = "contract"
    TEMPORARY = "temporary"
    INTERN = "intern"
    CONSULTANT = "consultant"

class EmploymentStatus(str, enum.Enum):
    ACTIVE = "active"
    INACTIVE = "inactive"
    ON_LEAVE = "on_leave"
    PROBATION = "probation"
    NOTICE_PERIOD = "notice_period"
    TERMINATED = "terminated"
    RESIGNED = "resigned"
    RETIRED = "retired"

class Gender(str, enum.Enum):
    MALE = "male"
    FEMALE = "female"
    OTHER = "other"
    PREFER_NOT_TO_SAY = "prefer_not_to_say"

class MaritalStatus(str, enum.Enum):
    SINGLE = "single"
    MARRIED = "married"
    DIVORCED = "divorced"
    WIDOWED = "widowed"
    SEPARATED = "separated"

class BloodGroup(str, enum.Enum):
    A_POSITIVE = "A+"
    A_NEGATIVE = "A-"
    B_POSITIVE = "B+"
    B_NEGATIVE = "B-"
    O_POSITIVE = "O+"
    O_NEGATIVE = "O-"
    AB_POSITIVE = "AB+"
    AB_NEGATIVE = "AB-"

class DocumentType(str, enum.Enum):
    CONTRACT = "contract"
    OFFER_LETTER = "offer_letter"
    APPOINTMENT_LETTER = "appointment_letter"
    RELIEVING_LETTER = "relieving_letter"
    EXPERIENCE_CERTIFICATE = "experience_certificate"
    CERTIFICATION = "certification"
    LICENSE = "license"
    EDUCATIONAL_DOCUMENT = "educational_document"
    IDENTITY_PROOF = "identity_proof"
    ADDRESS_PROOF = "address_proof"
    PERFORMANCE_REVIEW = "performance_review"
    WARNING_LETTER = "warning_letter"
    INCREMENT_LETTER = "increment_letter"
    OTHER = "other"

class ChangeType(str, enum.Enum):
    HIRE = "hire"
    PROMOTION = "promotion"
    TRANSFER = "transfer"
    DEMOTION = "demotion"
    SALARY_REVISION = "salary_revision"
    DEPARTMENT_CHANGE = "department_change"
    LOCATION_CHANGE = "location_change"
    DESIGNATION_CHANGE = "designation_change"
    REPORTING_CHANGE = "reporting_change"
    TERMINATION = "termination"
    RESIGNATION = "resignation"

class AlertType(str, enum.Enum):
    DOCUMENT_EXPIRY = "document_expiry"
    PROBATION_COMPLETION = "probation_completion"
    CONTRACT_RENEWAL = "contract_renewal"
    BIRTHDAY = "birthday"
    WORK_ANNIVERSARY = "work_anniversary"
    CERTIFICATION_EXPIRY = "certification_expiry"

class ContactRelationship(str, enum.Enum):
    FATHER = "father"
    MOTHER = "mother"
    SPOUSE = "spouse"
    SIBLING = "sibling"
    CHILD = "child"
    FRIEND = "friend"
    GUARDIAN = "guardian"
    OTHER = "other"


# ============================================================================
# CORE EMPLOYEE TABLE
# ============================================================================

class Employee(Base):
    """Core employee table with essential information"""
    __tablename__ = "employees"
    
    # Primary Keys and References
    id = Column(Integer, primary_key=True, index=True)
    uuid = Column(GUID(), default=uuid.uuid4, unique=True, nullable=False, index=True)
    organization_id = Column(Integer, ForeignKey('organization.id'), nullable=False, index=True)
    employee_code = Column(String(50), nullable=False, index=True)  # Unique within organization
    
    # Basic Personal Information
    first_name = Column(String(100), nullable=False)
    middle_name = Column(String(100), nullable=True)
    last_name = Column(String(100), nullable=False)
    preferred_name = Column(String(100), nullable=True)
    date_of_birth = Column(Date, nullable=True)
    gender = Column(Enum(Gender), nullable=True)
    marital_status = Column(Enum(MaritalStatus), nullable=True)
    blood_group = Column(Enum(BloodGroup), nullable=True)
    nationality = Column(String(100), nullable=True)
    
    # Contact Information
    personal_email = Column(String(255), nullable=True, index=True)
    work_email = Column(String(255), nullable=False, unique=True, index=True)
    mobile_number = Column(String(20), nullable=True)
    alternate_mobile_number = Column(String(20), nullable=True)
    work_phone = Column(String(20), nullable=True)
    work_phone_extension = Column(String(10), nullable=True)
    
    # Auth Fields
    hashed_password = Column(String(255), nullable=True)
    reset_password_token = Column(String(500), nullable=True)
    reset_password_token_expires_at = Column(DateTime, nullable=True)
    
    # Employment Information
    employment_type = Column(Enum(EmploymentType), nullable=False)
    employment_status = Column(Enum(EmploymentStatus), default=EmploymentStatus.ACTIVE, nullable=False, index=True)
    date_of_joining = Column(Date, nullable=False, index=True)
    date_of_confirmation = Column(Date, nullable=True)
    probation_end_date = Column(Date, nullable=True)
    notice_period_days = Column(Integer, default=30)
    date_of_leaving = Column(Date, nullable=True)
    
    # Job Information
    job_title_id = Column(Integer, ForeignKey('job_titles.id'), nullable=True)
    department_id = Column(Integer, ForeignKey('departments.id'), nullable=True, index=True)
    location_id = Column(Integer, ForeignKey('locations.id'), nullable=True, index=True)
    cost_center_id = Column(Integer, ForeignKey('cost_centers.id'), nullable=True)
    
    # Reporting Structure
    reporting_manager_id = Column(Integer, ForeignKey('employees.id'), nullable=True, index=True)
    functional_manager_id = Column(Integer, ForeignKey('employees.id'), nullable=True)
    
    # Media
    photograph_url = Column(String(500), nullable=True)
    signature_url = Column(String(500), nullable=True)
    
    # Language Preference
    preferred_language = Column(String(10), default='en', nullable=False)
    
    # Custom Fields (JSON for flexibility)
    custom_fields = Column(JSON, nullable=True)
    
    # Status Flags
    is_active = Column(Boolean, default=True, nullable=False, index=True)
    is_deleted = Column(Boolean, default=False, nullable=False)
    
    # Audit Fields
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    # User references commented out until User model is defined
    # created_by = Column(Integer, ForeignKey('users.id'), nullable=True)
    # updated_by = Column(Integer, ForeignKey('users.id'), nullable=True)
    deleted_at = Column(DateTime, nullable=True)
    # deleted_by = Column(Integer, ForeignKey('users.id'), nullable=True)
    
    # Relationships
    organization = relationship("Organization")
    job_title = relationship("JobTitle", foreign_keys=[job_title_id])
    department = relationship("Department", foreign_keys=[department_id])
    location = relationship("Location", foreign_keys=[location_id])
    reporting_manager = relationship("Employee", remote_side=[id], foreign_keys=[reporting_manager_id])
    functional_manager = relationship("Employee", remote_side=[id], foreign_keys=[functional_manager_id])
    documents = relationship("EmployeeDocument", back_populates="employee")
    
    @property
    def full_name(self) -> str:
        return f"{self.first_name} {self.last_name}"
        
    @property
    def email(self) -> str:
        return self.work_email
        
    @property
    def job_title_name(self) -> Optional[str]:
        return self.job_title.title_name if self.job_title else None
        
    @property
    def department_name(self) -> Optional[str]:
        return self.department.department_name if self.department else None
        
    @property
    def location_name(self) -> Optional[str]:
        return self.location.location_name if self.location else None
        
    @property
    def reporting_manager_name(self) -> Optional[str]:
        return self.reporting_manager.full_name if self.reporting_manager else None

    @property
    def is_password_set(self) -> bool:
        return self.hashed_password is not None and len(self.hashed_password) > 0

    # Composite Index for organization-specific queries
    __table_args__ = (
        Index('idx_org_emp_status', 'organization_id', 'employment_status'),
        Index('idx_org_emp_code', 'organization_id', 'employee_code', unique=True),
        Index('idx_org_active', 'organization_id', 'is_active'),
    )


# ============================================================================
# PERSONAL INFORMATION
# ============================================================================

class EmployeePersonalInfo(Base):
    """Extended personal information for employees"""
    __tablename__ = "employee_personal_info"
    
    id = Column(Integer, primary_key=True, index=True)
    employee_id = Column(Integer, ForeignKey('employees.id'), nullable=False, unique=True, index=True)
    
    # Identification Documents
    pan_number = Column(String(50), nullable=True)
    aadhar_number = Column(String(50), nullable=True)
    passport_number = Column(String(50), nullable=True)
    passport_expiry_date = Column(Date, nullable=True)
    passport_issue_country = Column(String(100), nullable=True)
    driving_license_number = Column(String(50), nullable=True)
    driving_license_expiry_date = Column(Date, nullable=True)
    social_security_number = Column(String(50), nullable=True)  # For international
    national_id_number = Column(String(50), nullable=True)
    
    # Additional Personal Details
    place_of_birth = Column(String(100), nullable=True)
    religion = Column(String(50), nullable=True)
    caste_category = Column(String(50), nullable=True)
    differently_abled = Column(Boolean, default=False)
    disability_details = Column(Text, nullable=True)
    
    # Physical Attributes (optional, based on requirements)
    height_cm = Column(Numeric(5, 2), nullable=True)
    weight_kg = Column(Numeric(5, 2), nullable=True)
    identification_marks = Column(Text, nullable=True)
    
    # Social Media
    linkedin_url = Column(String(500), nullable=True)
    twitter_handle = Column(String(100), nullable=True)
    facebook_url = Column(String(500), nullable=True)
    
    # Audit Fields
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


# ============================================================================
# ADDRESS INFORMATION
# ============================================================================

class EmployeeAddress(Base):
    """Employee addresses (current and permanent)"""
    __tablename__ = "employee_addresses"
    
    id = Column(Integer, primary_key=True, index=True)
    employee_id = Column(Integer, ForeignKey('employees.id'), nullable=False, index=True)
    address_type = Column(String(20), nullable=False)  # 'current', 'permanent', 'temporary'
    
    address_line1 = Column(String(255), nullable=False)
    address_line2 = Column(String(255), nullable=True)
    landmark = Column(String(255), nullable=True)
    city = Column(String(100), nullable=False)
    state = Column(String(100), nullable=False)
    country = Column(String(100), nullable=False)
    pincode = Column(String(20), nullable=False)
    
    is_primary = Column(Boolean, default=False)
    
    # Audit Fields
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    __table_args__ = (
        Index('idx_emp_addr_type', 'employee_id', 'address_type'),
    )


# ============================================================================
# EMERGENCY CONTACTS
# ============================================================================

class EmployeeEmergencyContact(Base):
    """Emergency contact information"""
    __tablename__ = "employee_emergency_contacts"
    
    id = Column(Integer, primary_key=True, index=True)
    employee_id = Column(Integer, ForeignKey('employees.id'), nullable=False, index=True)
    
    contact_name = Column(String(150), nullable=False)
    relationship = Column(Enum(ContactRelationship), nullable=False)
    primary_phone = Column(String(20), nullable=False)
    alternate_phone = Column(String(20), nullable=True)
    email = Column(String(255), nullable=True)
    address = Column(Text, nullable=True)
    
    is_primary = Column(Boolean, default=False)
    priority_order = Column(Integer, default=1)
    
    # Audit Fields
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


# ============================================================================
# ORGANIZATIONAL STRUCTURE
# ============================================================================

class Department(Base):
    """Departments within organization"""
    __tablename__ = "departments"
    
    id = Column(Integer, primary_key=True, index=True)
    uuid = Column(GUID(), default=uuid.uuid4, unique=True, nullable=False)
    organization_id = Column(Integer, ForeignKey('organization.id'), nullable=False, index=True)
    
    department_code = Column(String(50), nullable=False)
    department_name = Column(String(150), nullable=False)
    description = Column(Text, nullable=True)
    parent_department_id = Column(Integer, ForeignKey('departments.id'), nullable=True)
    head_of_department_id = Column(Integer, ForeignKey('employees.id'), nullable=True)
    
    is_active = Column(Boolean, default=True)
    
    # Relationships
    parent_department = relationship('Department', remote_side=[id], backref='sub_departments')
    head_of_department = relationship('Employee', foreign_keys=[head_of_department_id])
    
    @property
    def parent_department_uuid(self):
        return self.parent_department.uuid if self.parent_department else None
        
    @property
    def head_of_department_uuid(self):
        return self.head_of_department.uuid if self.head_of_department else None
    
    # Audit Fields
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    # created_by = Column(Integer, ForeignKey('users.id'), nullable=True)
    
    is_deleted = Column(Boolean, default=False, nullable=False)
    deleted_at = Column(DateTime, nullable=True)
    
    __table_args__ = (
        Index('idx_org_dept_code', 'organization_id', 'department_code', unique=True),
    )


class Location(Base):
    """Work locations/branches"""
    __tablename__ = "locations"
    
    id = Column(Integer, primary_key=True, index=True)
    uuid = Column(GUID(), default=uuid.uuid4, unique=True, nullable=False)
    organization_id = Column(Integer, ForeignKey('organization.id'), nullable=False, index=True)
    
    location_code = Column(String(50), nullable=False)
    location_name = Column(String(150), nullable=False)
    location_type = Column(String(50), nullable=True)  # 'head_office', 'branch', 'remote'
    
    address_line1 = Column(String(255), nullable=True)
    address_line2 = Column(String(255), nullable=True)
    city = Column(String(100), nullable=True)
    state = Column(String(100), nullable=True)
    country = Column(String(100), nullable=False)
    pincode = Column(String(20), nullable=True)
    
    phone = Column(String(20), nullable=True)
    email = Column(String(255), nullable=True)
    
    time_zone = Column(String(50), nullable=True)
    is_active = Column(Boolean, default=True)
    
    # Audit Fields
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    is_deleted = Column(Boolean, default=False, nullable=False)
    deleted_at = Column(DateTime, nullable=True)
    
    __table_args__ = (
        Index('idx_org_loc_code', 'organization_id', 'location_code', unique=True),
    )


class JobTitle(Base):
    """Job titles/designations"""
    __tablename__ = "job_titles"
    
    id = Column(Integer, primary_key=True, index=True)
    uuid = Column(GUID(), default=uuid.uuid4, unique=True, nullable=False)
    organization_id = Column(Integer, ForeignKey('organization.id'), nullable=False, index=True)
    
    title_code = Column(String(50), nullable=False)
    title_name = Column(String(150), nullable=False)
    job_level = Column(String(50), nullable=True)  # 'entry', 'mid', 'senior', 'executive'
    job_family = Column(String(100), nullable=True)  # 'engineering', 'sales', 'hr', etc.
    
    description = Column(Text, nullable=True)
    responsibilities = Column(Text, nullable=True)
    qualifications = Column(Text, nullable=True)
    
    is_active = Column(Boolean, default=True)
    
    # Audit Fields
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    is_deleted = Column(Boolean, default=False, nullable=False)
    deleted_at = Column(DateTime, nullable=True)
    
    __table_args__ = (
        Index('idx_org_title_code', 'organization_id', 'title_code', unique=True),
    )


class CostCenter(Base):
    """Cost centers for accounting"""
    __tablename__ = "cost_centers"
    
    id = Column(Integer, primary_key=True, index=True)
    uuid = Column(GUID(), default=uuid.uuid4, unique=True, nullable=False)
    organization_id = Column(Integer, ForeignKey('organization.id'), nullable=False, index=True)
    
    cost_center_code = Column(String(50), nullable=False)
    cost_center_name = Column(String(150), nullable=False)
    description = Column(Text, nullable=True)
    
    is_active = Column(Boolean, default=True)
    
    # Audit Fields
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    is_deleted = Column(Boolean, default=False, nullable=False)
    deleted_at = Column(DateTime, nullable=True)
    
    __table_args__ = (
        Index('idx_org_cc_code', 'organization_id', 'cost_center_code', unique=True),
    )


# ============================================================================
# DOCUMENT MANAGEMENT
# ============================================================================

class EmployeeDocument(Base):
    """Employee documents storage"""
    __tablename__ = "employee_documents"
    
    id = Column(Integer, primary_key=True, index=True)
    uuid = Column(GUID(), default=uuid.uuid4, unique=True, nullable=False)
    employee_id = Column(Integer, ForeignKey('employees.id'), nullable=False, index=True)
    
    document_type = Column(Enum(DocumentType), nullable=False)
    document_name = Column(String(255), nullable=False)
    document_number = Column(String(100), nullable=True)  # Certificate/License number
    description = Column(Text, nullable=True)
    
    file_name = Column(String(255), nullable=False)
    file_url = Column(String(500), nullable=False)
    file_size_kb = Column(Integer, nullable=True)
    mime_type = Column(String(100), nullable=True)
    
    issue_date = Column(Date, nullable=True)
    expiry_date = Column(Date, nullable=True, index=True)
    issuing_authority = Column(String(200), nullable=True)
    
    is_verified = Column(Boolean, default=False)
    # verified_by = Column(Integer, ForeignKey('users.id'), nullable=True)
    verified_at = Column(DateTime, nullable=True)
    verification_notes = Column(Text, nullable=True)
    
    is_confidential = Column(Boolean, default=False)
    
    # Audit Fields
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    # uploaded_by = Column(Integer, ForeignKey('users.id'), nullable=True)
    deleted_at = Column(DateTime, nullable=True)
    
    employee = relationship("Employee", back_populates="documents")
    
    __table_args__ = (
        Index('idx_emp_doc_type', 'employee_id', 'document_type'),
        Index('idx_doc_expiry', 'expiry_date'),
    )


# ============================================================================
# EMPLOYEE HISTORY TRACKING
# ============================================================================

class EmployeeHistory(Base):
    """Track all employee changes"""
    __tablename__ = "employee_history"
    
    id = Column(Integer, primary_key=True, index=True)
    uuid = Column(GUID(), default=uuid.uuid4, unique=True, nullable=False)
    employee_id = Column(Integer, ForeignKey('employees.id'), nullable=False, index=True)
    
    change_type = Column(Enum(ChangeType), nullable=False, index=True)
    effective_date = Column(Date, nullable=False, index=True)
    
    # Previous Values
    previous_job_title_id = Column(Integer, ForeignKey('job_titles.id'), nullable=True)
    previous_department_id = Column(Integer, ForeignKey('departments.id'), nullable=True)
    previous_location_id = Column(Integer, ForeignKey('locations.id'), nullable=True)
    previous_reporting_manager_id = Column(Integer, ForeignKey('employees.id'), nullable=True)
    previous_employment_type = Column(Enum(EmploymentType), nullable=True)
    previous_employment_status = Column(Enum(EmploymentStatus), nullable=True)
    previous_salary = Column(Numeric(15, 2), nullable=True)
    
    # New Values
    new_job_title_id = Column(Integer, ForeignKey('job_titles.id'), nullable=True)
    new_department_id = Column(Integer, ForeignKey('departments.id'), nullable=True)
    new_location_id = Column(Integer, ForeignKey('locations.id'), nullable=True)
    new_reporting_manager_id = Column(Integer, ForeignKey('employees.id'), nullable=True)
    new_employment_type = Column(Enum(EmploymentType), nullable=True)
    new_employment_status = Column(Enum(EmploymentStatus), nullable=True)
    new_salary = Column(Numeric(15, 2), nullable=True)
    
    reason = Column(Text, nullable=True)
    remarks = Column(Text, nullable=True)
    
    # Audit Fields
    created_at = Column(DateTime, default=datetime.utcnow)
    # created_by = Column(Integer, ForeignKey('users.id'), nullable=True)
    # approved_by = Column(Integer, ForeignKey('users.id'), nullable=True)
    approved_at = Column(DateTime, nullable=True)

    # Relationships
    previous_job_title = relationship("JobTitle", foreign_keys=[previous_job_title_id])
    new_job_title = relationship("JobTitle", foreign_keys=[new_job_title_id])
    previous_department = relationship("Department", foreign_keys=[previous_department_id])
    new_department = relationship("Department", foreign_keys=[new_department_id])
    previous_location = relationship("Location", foreign_keys=[previous_location_id])
    new_location = relationship("Location", foreign_keys=[new_location_id])
    previous_reporting_manager = relationship("Employee", foreign_keys=[previous_reporting_manager_id])
    new_reporting_manager = relationship("Employee", foreign_keys=[new_reporting_manager_id])


# ============================================================================
# CUSTOM FIELDS CONFIGURATION
# ============================================================================

class CustomFieldDefinition(Base):
    """Define custom fields for organization"""
    __tablename__ = "custom_field_definitions"
    
    id = Column(Integer, primary_key=True, index=True)
    uuid = Column(GUID(), default=uuid.uuid4, unique=True, nullable=False)
    organization_id = Column(Integer, ForeignKey('organization.id'), nullable=False, index=True)
    
    field_name = Column(String(100), nullable=False)
    field_label = Column(String(150), nullable=False)
    field_type = Column(String(50), nullable=False)  # 'text', 'number', 'date', 'dropdown', 'checkbox'
    field_options = Column(JSON, nullable=True)  # For dropdown values
    
    is_required = Column(Boolean, default=False)
    is_searchable = Column(Boolean, default=True)
    display_order = Column(Integer, default=0)
    
    is_active = Column(Boolean, default=True)
    
    # Audit Fields
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    is_deleted = Column(Boolean, default=False, nullable=False)
    deleted_at = Column(DateTime, nullable=True)
    
    __table_args__ = (
        Index('idx_org_custom_field', 'organization_id', 'field_name', unique=True),
    )


# ============================================================================
# ALERTS & NOTIFICATIONS
# ============================================================================

class EmployeeAlert(Base):
    """Automated alerts for important events"""
    __tablename__ = "employee_alerts"
    
    id = Column(Integer, primary_key=True, index=True)
    uuid = Column(GUID(), default=uuid.uuid4, unique=True, nullable=False)
    employee_id = Column(Integer, ForeignKey('employees.id'), nullable=False, index=True)
    
    alert_type = Column(Enum(AlertType), nullable=False, index=True)
    alert_date = Column(Date, nullable=False, index=True)
    alert_title = Column(String(255), nullable=False)
    alert_message = Column(Text, nullable=True)
    
    reference_type = Column(String(50), nullable=True)  # 'document', 'employee', 'contract'
    reference_id = Column(Integer, nullable=True)
    
    is_sent = Column(Boolean, default=False)
    sent_at = Column(DateTime, nullable=True)
    
    is_acknowledged = Column(Boolean, default=False)
    acknowledged_at = Column(DateTime, nullable=True)
    # acknowledged_by = Column(Integer, ForeignKey('users.id'), nullable=True)
    
    # Audit Fields
    created_at = Column(DateTime, default=datetime.utcnow)
    
    __table_args__ = (
        Index('idx_alert_date_type', 'alert_date', 'alert_type'),
        Index('idx_alert_pending', 'is_sent', 'alert_date'),
    )


# ============================================================================
# AUDIT LOG
# ============================================================================

class EmployeeAuditLog(Base):
    """Comprehensive audit trail for all employee data changes"""
    __tablename__ = "employee_audit_logs"
    
    id = Column(Integer, primary_key=True, index=True)
    uuid = Column(GUID(), default=uuid.uuid4, unique=True, nullable=False)
    
    employee_id = Column(Integer, ForeignKey('employees.id'), nullable=False, index=True)
    table_name = Column(String(100), nullable=False, index=True)
    record_id = Column(Integer, nullable=False)
    
    action = Column(String(20), nullable=False)  # 'INSERT', 'UPDATE', 'DELETE'
    field_name = Column(String(100), nullable=True)
    old_value = Column(Text, nullable=True)
    new_value = Column(Text, nullable=True)
    
    change_summary = Column(Text, nullable=True)
    ip_address = Column(String(50), nullable=True)
    user_agent = Column(String(500), nullable=True)
    
    # Audit Fields
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    # created_by = Column(Integer, ForeignKey('users.id'), nullable=True)
    
    __table_args__ = (
        Index('idx_audit_emp_table', 'employee_id', 'table_name'),
        Index('idx_audit_created', 'created_at'),
    )


# ============================================================================
# EDUCATION & CERTIFICATIONS
# ============================================================================

class EmployeeEducation(Base):
    """Educational qualifications"""
    __tablename__ = "employee_education"
    
    id = Column(Integer, primary_key=True, index=True)
    employee_id = Column(Integer, ForeignKey('employees.id'), nullable=False, index=True)
    
    degree_name = Column(String(150), nullable=False)
    field_of_study = Column(String(150), nullable=True)
    institution_name = Column(String(255), nullable=False)
    university_name = Column(String(255), nullable=True)
    
    start_date = Column(Date, nullable=True)
    end_date = Column(Date, nullable=True)
    graduation_year = Column(Integer, nullable=True)
    
    grade_percentage = Column(Numeric(5, 2), nullable=True)
    cgpa = Column(Numeric(4, 2), nullable=True)
    
    is_highest_qualification = Column(Boolean, default=False)
    
    # Audit Fields
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    employee = relationship("Employee")

class EmployeeCertification(Base):
    """Professional certifications"""
    __tablename__ = "employee_certifications"
    
    id = Column(Integer, primary_key=True, index=True)
    employee_id = Column(Integer, ForeignKey('employees.id'), nullable=False, index=True)
    
    certification_name = Column(String(255), nullable=False)
    issuing_organization = Column(String(255), nullable=False)
    certification_id = Column(String(100), nullable=True)
    
    issue_date = Column(Date, nullable=True)
    expiry_date = Column(Date, nullable=True, index=True)
    
    credential_url = Column(String(500), nullable=True)
    
    is_active = Column(Boolean, default=True)
    
    # Audit Fields
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    employee = relationship("Employee")


# ============================================================================
# WORK EXPERIENCE (Previous)
# ============================================================================

class EmployeeWorkExperience(Base):
    """Previous work experience"""
    __tablename__ = "employee_work_experience"
    
    id = Column(Integer, primary_key=True, index=True)
    employee_id = Column(Integer, ForeignKey('employees.id'), nullable=False, index=True)
    
    company_name = Column(String(255), nullable=False)
    job_title = Column(String(150), nullable=False)
    employment_type = Column(String(50), nullable=True)
    
    start_date = Column(Date, nullable=False)
    end_date = Column(Date, nullable=True)
    is_current = Column(Boolean, default=False)
    
    location = Column(String(150), nullable=True)
    description = Column(Text, nullable=True)
    
    reason_for_leaving = Column(Text, nullable=True)
    
    # Audit Fields
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
