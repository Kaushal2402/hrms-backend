import uuid
from datetime import datetime
from sqlalchemy import Column, String, Boolean, DateTime, Enum, Integer, ForeignKey
from sqlalchemy.types import TypeDecorator, CHAR
import uuid
import enum
from app.db.base_class import Base

class GUID(TypeDecorator):
    """Platform-independent GUID type.
    Uses PostgreSQL's UUID type for PostgreSQL,
    otherwise uses CHAR(36), storing as stringified hex values.
    """
    impl = CHAR
    cache_ok = True

    def __init__(self, *args, **kwargs):
        kwargs.pop('as_uuid', None)
        super(GUID, self).__init__(*args, **kwargs)

    def load_dialect_impl(self, dialect):
        if dialect.name == 'postgresql':
            from sqlalchemy.dialects.postgresql import UUID
            return dialect.type_descriptor(UUID())
        else:
            return dialect.type_descriptor(CHAR(36))

    def process_bind_param(self, value, dialect):
        if value is None:
            return value
        elif dialect.name == 'postgresql':
            return str(value)
        else:
            if not isinstance(value, uuid.UUID):
                return str(uuid.UUID(value))
            else:
                # return "%.32x" % value.int
                return str(value)

    def process_result_value(self, value, dialect):
        if value is None:
            return value
        else:
            if not isinstance(value, uuid.UUID):
                return uuid.UUID(value)
            else:
                return value

class OrganizationStatus(str, enum.Enum):
    VERIFICATION_PENDING = "verification_pending"
    ACTIVE = "active"
    INACTIVE = "inactive"
    SUSPENDED = "suspended"
    TRIAL = "trial"

class OrganizationSize(str, enum.Enum):
    SIZE_1_10 = "1-10"
    SIZE_11_50 = "11-50"
    SIZE_51_200 = "51-200"
    SIZE_201_500 = "201-500"
    SIZE_500_PLUS = "500+"

class Industry(Base):
    __tablename__ = "industries"
    
    id = Column(Integer, primary_key=True, index=True)
    uuid = Column(GUID(), default=uuid.uuid4, unique=True, nullable=False, index=True)
    
    name = Column(String(100), unique=True, nullable=False, index=True)
    description = Column(String(500), nullable=True)
    icon = Column(String(50), nullable=True)
    is_active = Column(Boolean, default=True, index=True)
    
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class Organization(Base):
    id = Column(Integer, primary_key=True, index=True)
    uuid = Column(GUID(), default=uuid.uuid4, unique=True, nullable=False, index=True)
    
    name = Column(String(255), nullable=False)
    legal_name = Column(String(255), unique=True, nullable=False)
    email = Column(String(255), unique=True, nullable=False, index=True)
    phone = Column(String(50), unique=True, nullable=False)
    website = Column(String(255), nullable=True)
    logo = Column(String(255), nullable=True)
    
    industry = Column(String(100), nullable=True) # Check if we want strictly dropdown values or just string
    industry_id = Column(Integer, ForeignKey('industries.id'), nullable=True)
    organization_size = Column(Enum(OrganizationSize), default=OrganizationSize.SIZE_1_10, nullable=False)
    founded_year = Column(Integer, nullable=True)
    
    gst_number = Column(String(50), nullable=True)
    pan_number = Column(String(50), nullable=True)
    
    address_line1 = Column(String(255), nullable=True)
    address_line2 = Column(String(255), nullable=True)
    city = Column(String(100), nullable=True)
    state = Column(String(100), nullable=True)
    country = Column(String(100), nullable=True)
    pincode = Column(String(20), nullable=True)
    
    status = Column(Enum(OrganizationStatus), default=OrganizationStatus.TRIAL, nullable=False)
    is_verified = Column(Boolean, default=False)
    trial_ends_at = Column(DateTime, nullable=True)

    hashed_password = Column(String(255), nullable=True)
    
    # Internal for OTP
    verification_code = Column(String(10), nullable=True)
    verification_code_expires_at = Column(DateTime, nullable=True)

    # Reset Password
    reset_password_token = Column(String(500), nullable=True)
    reset_password_token_expires_at = Column(DateTime, nullable=True)
    
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    deleted_at = Column(DateTime, nullable=True)
