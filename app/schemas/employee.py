from pydantic import BaseModel, UUID4, EmailStr, field_validator, model_validator, computed_field, ConfigDict
from typing import Optional, List, Generic, TypeVar, Any
from datetime import date, datetime, timedelta
import enum
from app.schemas.department import PaginatedResponse, DepartmentSchema
from app.schemas.job_title import JobTitleSchema
from app.schemas.location import LocationSchema
from app.schemas.rbac import Role


# Re-defining Enums to avoid ORM dependency in schemas and ensure loose coupling
class Gender(str, enum.Enum):
    MALE = "male"
    FEMALE = "female"
    OTHER = "other"
    PREFER_NOT_TO_SAY = "prefer_not_to_say"

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

class MaritalStatus(str, enum.Enum):
    SINGLE = "single"
    MARRIED = "married"
    DIVORCED = "divorced"
    WIDOWED = "widowed"
    SEPARATED = "separated"

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

class BloodGroup(str, enum.Enum):
    A_POSITIVE = "A+"
    A_NEGATIVE = "A-"
    B_POSITIVE = "B+"
    B_NEGATIVE = "B-"
    O_POSITIVE = "O+"
    O_NEGATIVE = "O-"
    AB_POSITIVE = "AB+"
    AB_NEGATIVE = "AB-"

class EmployeeBase(BaseModel):
    # Personal Info
    first_name: str
    last_name: str
    middle_name: Optional[str] = None
    preferred_name: Optional[str] = None
    date_of_birth: date
    gender: Gender
    marital_status: Optional[MaritalStatus] = None
    blood_group: Optional[BloodGroup] = None
    nationality: Optional[str] = None
    
    # Contact Info
    work_email: EmailStr
    personal_email: Optional[EmailStr] = None
    mobile_number: str
    alternate_mobile_number: Optional[str] = None
    work_phone: Optional[str] = None
    work_phone_extension: Optional[str] = None
    
    # Employment Info
    employee_code: Optional[str] = None
    employment_type: EmploymentType
    employment_status: EmploymentStatus
    date_of_joining: date
    date_of_confirmation: Optional[date] = None # User asked required, but usually depends on status. I'll make it Optional here but validate if needed? Prompt said REQUIRED. I will make it required_in_create.
    probation_end_date: Optional[date] = None
    notice_period_days: Optional[int] = 30
    date_of_leaving: Optional[date] = None
    
    # IDs (Assuming Input is UUIDs for foreign keys in API)
    # But Base usually reflects model. Create overrides.
    # I'll put specific ID fields in Create.

    is_active: Optional[bool] = True
    photograph_url: Optional[str] = None

class EmployeeCreate(EmployeeBase):
    personal_email: EmailStr  # Required per prompt
    date_of_confirmation: date # Required per prompt
    
    # UUIDs for related entities
    job_title_id: UUID4 
    department_id: UUID4
    location_id: UUID4
    reporting_manager_id: Optional[str] = None
    role_uuid: UUID4
    
    @field_validator('first_name', 'last_name')
    @classmethod
    def name_not_empty(cls, v):
        if not v or not v.strip():
            raise ValueError('Name field must not be empty')
        return v

    @field_validator('date_of_birth')
    @classmethod
    def validate_dob(cls, v):
        if v and v > date.today():
            raise ValueError('Date of birth must be in the past or today')
        return v

    @field_validator('date_of_joining')
    @classmethod
    def validate_joining_date(cls, v):
        if v:
            max_future = date.today() + timedelta(days=91) # approx 3 months
            if v > max_future:
                raise ValueError('Date of joining cannot be more than 3 months in the future')
        return v

    @field_validator('date_of_confirmation')
    @classmethod
    def validate_confirmation_date(cls, v):
        if v and v > date.today():
            raise ValueError('Date of confirmation must be in the past or today')
        return v
    
class EmployeeUpdate(BaseModel):
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    middle_name: Optional[str] = None
    preferred_name: Optional[str] = None
    date_of_birth: Optional[date] = None
    gender: Optional[Gender] = None
    marital_status: Optional[MaritalStatus] = None
    blood_group: Optional[BloodGroup] = None
    nationality: Optional[str] = None
    
    # Contact Info
    personal_email: Optional[EmailStr] = None
    mobile_number: Optional[str] = None
    alternate_mobile_number: Optional[str] = None
    work_phone: Optional[str] = None
    work_phone_extension: Optional[str] = None
    
    # Employment Info
    employment_type: Optional[EmploymentType] = None
    employment_status: Optional[EmploymentStatus] = None
    date_of_joining: Optional[date] = None
    date_of_confirmation: Optional[date] = None
    probation_end_date: Optional[date] = None
    notice_period_days: Optional[int] = None
    date_of_leaving: Optional[date] = None
    
    # IDs
    job_title_id: Optional[UUID4] = None
    department_id: Optional[UUID4] = None
    location_id: Optional[UUID4] = None
    reporting_manager_id: Optional[UUID4] = None
    
    is_active: Optional[bool] = None
    role_uuid: Optional[UUID4] = None

    @field_validator('first_name', 'last_name', 'middle_name')
    @classmethod
    def trim_names(cls, v):
        if isinstance(v, str):
            return v.strip() or None
        return v

    @field_validator('date_of_birth')
    @classmethod
    def validate_dob(cls, v):
        if v and v > date.today():
            raise ValueError('Date of birth must be in the past or today')
        return v

    @field_validator('date_of_joining')
    @classmethod
    def validate_joining_date(cls, v):
        if v:
            max_future = date.today() + timedelta(days=91) # approx 3 months
            if v > max_future:
                raise ValueError('Date of joining cannot be more than 3 months in the future')
        return v

    @field_validator('date_of_confirmation')
    @classmethod
    def validate_confirmation_date(cls, v):
        if v and v > date.today():
            raise ValueError('Date of confirmation must be in the past or today')
        return v

class EmployeeSummarySchema(BaseModel):
    uuid: UUID4
    first_name: str
    last_name: str
    job_title: Optional[JobTitleSchema] = None
    department: Optional[DepartmentSchema] = None
    is_password_set: bool = False
    photograph_url: Optional[str] = None
    
    class Config:
        from_attributes = True

class EmployeeSchema(EmployeeBase):
    id: int
    uuid: UUID4
    
    # Relationships (Returning Objects)
    job_title: Optional[JobTitleSchema] = None
    department: Optional[DepartmentSchema] = None
    location: Optional[LocationSchema] = None
    reporting_manager: Optional[EmployeeSummarySchema] = None
    functional_manager: Optional[EmployeeSummarySchema] = None
    role: Optional[Role] = None
    is_password_set: bool = False
    
    # We remove the _id fields that returned UUIDs, fulfilling the request to "share the object"
    
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    
    class Config:
        from_attributes = True

class EmployeeResponse(BaseModel):
    success: bool
    message: str
    data: Optional[EmployeeSchema] = None

class EmployeeDetailSchema(EmployeeSchema):
    # Inherits everything from EmployeeSchema including nested objects
    pass

class EmployeeDetailResponse(BaseModel):
    success: bool
    message: str
    data: Optional[EmployeeDetailSchema] = None

# ... (other classes if any)

# Rebuild models for forward refs
EmployeeSchema.model_rebuild()
EmployeeDetailSchema.model_rebuild()

class EmployeeListResponse(PaginatedResponse[List[EmployeeSchema]]):
    pass

class EmployeeDeleteResponse(BaseModel):
    success: bool
    message: str
    data: Optional[Any] = None

class EmployeeImportError(BaseModel):
    row: int
    error: str
    data: Optional[Any] = None

class EmployeeImportResponse(BaseModel):
    success: bool
    message: str
    success_count: int
    error_count: int
    errors: List[EmployeeImportError] = []

# ==========================
# Personal Info Schemas
# ==========================

class PersonalInfoBase(BaseModel):
    pan_number: Optional[str] = None
    aadhar_number: Optional[str] = None
    passport_number: Optional[str] = None
    passport_expiry_date: Optional[date] = None
    passport_issue_country: Optional[str] = None
    
    driving_license_number: Optional[str] = None
    driving_license_expiry_date: Optional[date] = None
    
    social_security_number: Optional[str] = None
    national_id_number: Optional[str] = None
    
    place_of_birth: Optional[str] = None
    religion: Optional[str] = None
    caste_category: Optional[str] = None
    
    differently_abled: Optional[bool] = False
    disability_details: Optional[str] = None
    
    height_cm: Optional[float] = None
    weight_kg: Optional[float] = None
    identification_marks: Optional[str] = None
    
    linkedin_url: Optional[str] = None
    twitter_handle: Optional[str] = None
    facebook_url: Optional[str] = None

    @field_validator('linkedin_url', 'twitter_handle', 'facebook_url')
    @classmethod
    def validate_url(cls, v):
        if v and v.strip():
            if not (v.startswith('http://') or v.startswith('https://')):
                raise ValueError('Must be a valid URL starting with http:// or https://')
        return v

class PersonalInfoCreate(PersonalInfoBase):
    pass

class PersonalInfoUpdate(PersonalInfoBase):
    pass

class PersonalInfoSchema(PersonalInfoBase):
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    
    class Config:
        from_attributes = True

class PersonalInfoResponse(BaseModel):
    success: bool
    message: str
    data: Optional[PersonalInfoSchema] = None

# ==========================
# Address Schemas
# ==========================

class AddressType(str, enum.Enum):
    CURRENT = "current"
    PERMANENT = "permanent"
    TEMPORARY = "temporary"

class AddressBase(BaseModel):
    address_type: AddressType
    address_line1: str
    address_line2: Optional[str] = None
    landmark: Optional[str] = None
    city: str
    state: str
    country: str
    pincode: str
    is_primary: Optional[bool] = False

class AddressCreate(AddressBase):
    pass

class AddressUpdate(AddressBase):
    pass

class AddressSchema(AddressBase):
    id: int
    
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    
    class Config:
        from_attributes = True

class AddressResponse(BaseModel):
    success: bool
    message: str
    data: Optional[AddressSchema] = None

class AddressListResponse(BaseModel):
    success: bool
    message: str
    data: List[AddressSchema] = []

# ==========================
# Emergency Contact Schemas
# ==========================

class ContactRelationship(str, enum.Enum):
    FATHER = "father"
    MOTHER = "mother"
    SPOUSE = "spouse"
    SIBLING = "sibling"
    CHILD = "child"
    FRIEND = "friend"
    GUARDIAN = "guardian"
    OTHER = "other"

class EmergencyContactBase(BaseModel):
    contact_name: str
    relationship: ContactRelationship
    primary_phone: str
    alternate_phone: Optional[str] = None
    email: Optional[EmailStr] = None
    address: Optional[str] = None
    is_primary: Optional[bool] = False
    priority_order: Optional[int] = 1

class EmergencyContactCreate(EmergencyContactBase):
    pass

class EmergencyContactUpdate(EmergencyContactBase):
    pass

class EmergencyContactSchema(EmergencyContactBase):
    id: int
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    
    class Config:
        from_attributes = True

class EmergencyContactResponse(BaseModel):
    success: bool
    message: str
    data: Optional[EmergencyContactSchema] = None

class EmergencyContactListResponse(BaseModel):
    success: bool
    message: str
    data: List[EmergencyContactSchema] = []

# ==========================
# Education Schemas
# ==========================

class EducationBase(BaseModel):
    degree_name: str
    field_of_study: Optional[str] = None
    institution_name: str
    university_name: Optional[str] = None
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    graduation_year: Optional[int] = None
    grade_percentage: Optional[float] = None
    cgpa: Optional[float] = None
    is_highest_qualification: Optional[bool] = False

class EducationCreate(EducationBase):
    pass

class EducationUpdate(EducationBase):
    pass

class EducationSchema(EducationBase):
    id: int
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    
    class Config:
        from_attributes = True

class EducationResponse(BaseModel):
    success: bool
    message: str
    data: Optional[EducationSchema] = None

class EducationListResponse(BaseModel):
    success: bool
    message: str
    data: List[EducationSchema] = []

# ==========================
# Certification Schemas
# ==========================

class CertificationBase(BaseModel):
    certification_name: str
    issuing_organization: str
    certification_id: Optional[str] = None
    issue_date: Optional[date] = None
    expiry_date: Optional[date] = None
    credential_url: Optional[str] = None
    is_active: Optional[bool] = True

class CertificationCreate(CertificationBase):
    pass

class CertificationUpdate(CertificationBase):
    pass

class CertificationSchema(CertificationBase):
    id: int
    employee_id: int
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    
    class Config:
        from_attributes = True

class CertificationResponse(BaseModel):
    success: bool
    message: str
    data: Optional[CertificationSchema] = None

class CertificationListResponse(BaseModel):
    success: bool
    message: str
    data: List[CertificationSchema] = []


class ExpiringCertificationSchema(CertificationSchema):
    employee: EmployeeSummarySchema

class ExpiringCertificationListResponse(BaseModel):
    success: bool
    message: str
    data: List[ExpiringCertificationSchema] = []

# ==========================
# Work Experience Schemas
# ==========================

class WorkExperienceBase(BaseModel):
    company_name: str
    job_title: str
    employment_type: Optional[str] = None
    start_date: date
    end_date: Optional[date] = None
    is_current: Optional[bool] = False
    location: Optional[str] = None
    description: Optional[str] = None
    reason_for_leaving: Optional[str] = None

class WorkExperienceCreate(WorkExperienceBase):
    pass

class WorkExperienceUpdate(WorkExperienceBase):
    pass

class WorkExperienceSchema(WorkExperienceBase):
    id: int
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    
    class Config:
        from_attributes = True

class WorkExperienceResponse(BaseModel):
    success: bool
    message: str
    data: Optional[WorkExperienceSchema] = None

class WorkExperienceListResponse(BaseModel):
    success: bool
    message: str
    data: List[WorkExperienceSchema] = []

# ==========================
# Org Chart Schemas
# ==========================

class OrgChartNode(BaseModel):
    entity_type: str = "employee" # "organization" or "employee"
    id: Optional[str] = None
    name: Optional[str] = None
    employee: Optional[EmployeeSummarySchema] = None
    children: List['OrgChartNode'] = []
    
    model_config = ConfigDict(from_attributes=True)

class OrgChartResponse(BaseModel):
    success: bool
    message: str
    data: List[OrgChartNode] = []

OrgChartNode.model_rebuild()

class ReportingStructureData(BaseModel):
    employee: EmployeeSummarySchema
    reporting_chain: List[EmployeeSummarySchema]
    direct_reports: List[EmployeeSummarySchema]

class ReportingStructureResponse(BaseModel):
    success: bool
    message: str
    data: Optional[ReportingStructureData] = None

# ==========================
# History Schemas
# ==========================

class EmployeeHistorySchema(BaseModel):
    id: int
    change_type: ChangeType
    effective_date: date
    
    previous_job_title: Optional[JobTitleSchema] = None
    new_job_title: Optional[JobTitleSchema] = None
    
    previous_department: Optional[DepartmentSchema] = None
    new_department: Optional[DepartmentSchema] = None
    
    previous_location: Optional[LocationSchema] = None
    new_location: Optional[LocationSchema] = None
    
    # Manager is Employee, using Summary to avoid cycles/depth issues
    previous_reporting_manager: Optional[EmployeeSummarySchema] = None
    new_reporting_manager: Optional[EmployeeSummarySchema] = None

    previous_salary: Optional[float] = None
    new_salary: Optional[float] = None
    
    reason: Optional[str] = None
    remarks: Optional[str] = None
    
    class Config:
        from_attributes = True

class EmployeeHistoryCreate(BaseModel):
    change_type: ChangeType
    effective_date: date
    
    previous_job_title_uuid: Optional[UUID4] = None
    new_job_title_uuid: Optional[UUID4] = None
    
    previous_department_uuid: Optional[UUID4] = None
    new_department_uuid: Optional[UUID4] = None
    
    previous_location_uuid: Optional[UUID4] = None
    new_location_uuid: Optional[UUID4] = None
    
    previous_reporting_manager_uuid: Optional[UUID4] = None
    new_reporting_manager_uuid: Optional[UUID4] = None

    previous_salary: Optional[float] = None
    new_salary: Optional[float] = None
    
    previous_employment_type: Optional[EmploymentType] = None
    new_employment_type: Optional[EmploymentType] = None
    
    previous_employment_status: Optional[EmploymentStatus] = None
    new_employment_status: Optional[EmploymentStatus] = None
    
    reason: Optional[str] = None
    remarks: Optional[str] = None

class EmployeeHistoryUpdate(BaseModel):
    change_type: Optional[ChangeType] = None
    effective_date: Optional[date] = None
    
    previous_job_title_uuid: Optional[UUID4] = None
    new_job_title_uuid: Optional[UUID4] = None
    
    previous_department_uuid: Optional[UUID4] = None
    new_department_uuid: Optional[UUID4] = None
    
    previous_location_uuid: Optional[UUID4] = None
    new_location_uuid: Optional[UUID4] = None
    
    previous_reporting_manager_uuid: Optional[UUID4] = None
    new_reporting_manager_uuid: Optional[UUID4] = None

    previous_salary: Optional[float] = None
    new_salary: Optional[float] = None
    
    previous_employment_type: Optional[EmploymentType] = None
    new_employment_type: Optional[EmploymentType] = None
    
    previous_employment_status: Optional[EmploymentStatus] = None
    new_employment_status: Optional[EmploymentStatus] = None
    
    reason: Optional[str] = None
    remarks: Optional[str] = None

class EmployeeHistoryResponse(BaseModel):
    success: bool
    message: str
    data: Optional[EmployeeHistorySchema] = None

class EmployeeHistoryListResponse(PaginatedResponse[List[EmployeeHistorySchema]]):
    pass

# ==========================
# Summary Card Schemas
# ==========================

class EmployeeSummaryCardSchema(BaseModel):
    uuid: UUID4
    employee_code: str
    first_name: str
    last_name: str
    middle_name: Optional[str] = None
    
    # Org Info
    job_title_name: Optional[str] = None
    department_name: Optional[str] = None
    location_name: Optional[str] = None
    reporting_manager_name: Optional[str] = None
    
    @computed_field
    @property
    def full_name(self) -> str:
        return f"{self.first_name} {self.last_name}"
        
    @computed_field
    @property
    def job_title(self) -> Optional[str]:
        return self.job_title_name
        
    @computed_field
    @property
    def department(self) -> Optional[str]:
        return self.department_name
        
    @computed_field
    @property
    def location(self) -> Optional[str]:
        return self.location_name
    
    # Employment Info
    employment_status: EmploymentStatus
    employment_type: EmploymentType
    date_of_joining: date
    
    # Contact Info
    work_email: EmailStr
    mobile_number: Optional[str] = None
    
    # Media
    photograph_url: Optional[str] = None

    class Config:
        from_attributes = True

class EmployeeSummaryCardResponse(BaseModel):
    success: bool
    message: str
    data: Optional[EmployeeSummaryCardSchema] = None

# Document Schemas
# ==========================

class EmployeeMinimalSchema(BaseModel):
    uuid: UUID4
    first_name: str
    last_name: str
    job_title_name: Optional[str] = None
    department_name: Optional[str] = None
    photograph_url: Optional[str] = None
    
    @computed_field
    @property
    def name(self) -> str:
        return f"{self.first_name} {self.last_name}"
    
    @computed_field
    @property
    def job_title(self) -> Optional[str]:
        return self.job_title_name
        
    @computed_field
    @property
    def department(self) -> Optional[str]:
        return self.department_name

    class Config:
        from_attributes = True
        # To include properties in dict/json output, we often need to use getters or pydantic v2 computed_field
        # For simplicity in this project (likely Pydantic v2), I'll try to keep it standard.

class EmployeeDocumentSchema(BaseModel):
    id: int
    uuid: UUID4
    employee_id: int
    document_type: DocumentType
    document_name: str
    document_number: Optional[str] = None
    description: Optional[str] = None
    
    file_name: str
    file_url: str
    file_size_kb: Optional[int] = None
    mime_type: Optional[str] = None
    
    issue_date: Optional[date] = None
    expiry_date: Optional[date] = None
    issuing_authority: Optional[str] = None
    created_at: Optional[datetime] = None
    
    is_verified: bool = False
    verified_at: Optional[datetime] = None
    verification_notes: Optional[str] = None
    
    class Config:
        from_attributes = True

class EmployeeDocumentWithEmployeeSchema(EmployeeDocumentSchema):
    employee: Optional[EmployeeMinimalSchema] = None


class EmployeeDocumentUpdate(BaseModel):
    document_type: Optional[DocumentType] = None
    document_name: Optional[str] = None
    document_number: Optional[str] = None
    description: Optional[str] = None
    issue_date: Optional[date] = None
    expiry_date: Optional[date] = None
    issuing_authority: Optional[str] = None
    is_verified: Optional[bool] = None
    verification_notes: Optional[str] = None

class DocumentVerification(BaseModel):
    verification_notes: Optional[str] = None
    is_verified: bool = True

class EmployeeDocumentResponse(BaseModel):
    success: bool
    message: str
    data: Optional[EmployeeDocumentSchema] = None

class EmployeeDocumentListResponse(BaseModel):
    success: bool
    message: str
    data: List[EmployeeDocumentWithEmployeeSchema] = []

