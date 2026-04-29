from typing import Optional, Union
from uuid import UUID
from datetime import datetime
from pydantic import BaseModel, EmailStr, constr, validator
from app.models.organization import OrganizationSize, OrganizationStatus
from app.utils.upload import get_file_url

# Shared rules
def validate_year(v):
    if v and v > datetime.now().year:
        raise ValueError('Founded year cannot be in the future')
    return v

# Base properties
class OrganizationBase(BaseModel):
    name: Optional[str] = None
    legal_name: Optional[str] = None
    email: Optional[EmailStr] = None
    phone: Optional[str] = None
    phone: Optional[str] = None
    organization_size: Optional[OrganizationSize] = OrganizationSize.SIZE_1_10
    logo: Optional[str] = None
    
    website: Optional[str] = None
    industry: Optional[str] = None
    founded_year: Optional[int] = None
    
    gst_number: Optional[str] = None
    pan_number: Optional[str] = None
    
    address_line1: Optional[str] = None
    address_line2: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    country: Optional[str] = None
    pincode: Optional[str] = None

# Properties to receive on registration
class OrganizationRegister(BaseModel):
    name: str
    legal_name: str
    email: EmailStr
    phone: str
    organization_size: OrganizationSize = OrganizationSize.SIZE_1_10

# Properties to receive on update
class OrganizationUpdate(BaseModel):
    name: Optional[str] = None
    organization_size: Optional[OrganizationSize] = None
    website: Optional[str] = None
    industry: Optional[str] = None
    founded_year: Optional[int] = None
    
    gst_number: Optional[str] = None
    pan_number: Optional[str] = None
    
    address_line1: Optional[str] = None
    address_line2: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    country: Optional[str] = None
    pincode: Optional[str] = None
    
    # Intentionally EXCLUDING legal_name, email, phone from simple updates because they are restricted/unique
    # But user requirements say "not allowed to update... [legal_name, email, phone]"
    # However, sometimes users might need to change them (but requires special care usually). 
    # The requirement says "not allowed to update", so I will NOT put them here or handle them strictly.
    
    @validator('founded_year')
    def validate_founded_year(cls, v):
        return validate_year(v)

# Properties shared by models stored in DB
class OrganizationInDBBase(OrganizationBase):
    name: str # override optional
    legal_name: str
    email: EmailStr
    phone: str
    
    uuid: Union[str, UUID]
    status: OrganizationStatus
    is_verified: bool
    trial_ends_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

    @validator('logo', pre=True, always=True)
    def logo_url(cls, v):
        if v:
            return get_file_url(v)
        return v

# Properties to return to client
class Organization(OrganizationInDBBase):
    pass
    
# Additional properties stored in DB
class OrganizationInDB(OrganizationInDBBase):
    id: int
    verification_code: Optional[str] = None
    verification_code_expires_at: Optional[datetime] = None

class OrganizationVerifyOTP(BaseModel):
    email: EmailStr
    otp: str

class OrganizationResendOTP(BaseModel):
    email: EmailStr
