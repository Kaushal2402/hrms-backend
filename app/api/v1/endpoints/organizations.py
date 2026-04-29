import random
import string
from datetime import datetime, timedelta
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks, status
from sqlalchemy.orm import Session
from sqlalchemy import or_

from app.api import deps
from app.models.organization import Organization, OrganizationStatus
from app.models.employee import Employee
from app.schemas.organization import (
    OrganizationRegister, 
    OrganizationVerifyOTP, 
    Organization as OrganizationSchema,
    OrganizationResendOTP,
    OrganizationUpdate
)
from app.utils.email import send_otp_email, send_welcome_email
from app.core import security

router = APIRouter()

def generate_otp(length=6):
    return ''.join(random.choices(string.digits, k=length))

def generate_password(length=8):
    return ''.join(random.choices(string.ascii_letters + string.digits, k=length))

@router.post("/register", status_code=status.HTTP_201_CREATED)
def register_organization(
    *,
    db: Session = Depends(deps.get_db),
    org_in: OrganizationRegister,
    background_tasks: BackgroundTasks
):
    """
    Register a new organization and send verification OTP.
    """
    # Separate validation checks
    # Check if email is used by an Employee
    if db.query(Employee).filter(or_(Employee.work_email == org_in.email, Employee.personal_email == org_in.email)).first():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="The email address is already in use."
        )

    existing_org = db.query(Organization).filter(Organization.email == org_in.email).first()
    if existing_org and existing_org.status != OrganizationStatus.VERIFICATION_PENDING:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="The email address is already in use."
        )

    phone_query = db.query(Organization).filter(Organization.phone == org_in.phone)
    if existing_org:
        phone_query = phone_query.filter(Organization.id != existing_org.id)
    if phone_query.first():
        raise HTTPException(
            status_code=400,
            detail="The phone number is already in use."
        )

    legal_name_query = db.query(Organization).filter(Organization.legal_name == org_in.legal_name)
    if existing_org:
        legal_name_query = legal_name_query.filter(Organization.id != existing_org.id)
    if legal_name_query.first():
        raise HTTPException(
            status_code=400,
            detail="The legal name is already in use."
        )
    # Create or Update Org
    otp = generate_otp()
    otp_expires = datetime.utcnow() + timedelta(minutes=10)
    
    if existing_org:
        # Update existing record
        for key, value in org_in.model_dump().items():
            setattr(existing_org, key, value)
        existing_org.verification_code = otp
        existing_org.verification_code_expires_at = otp_expires
        db_org = existing_org
    else:
        # Create new record
        db_org = Organization(
            **org_in.model_dump(),
            status=OrganizationStatus.VERIFICATION_PENDING,
            verification_code=otp,
            verification_code_expires_at=otp_expires
        )
        db.add(db_org)
        
    db.commit()
    db.refresh(db_org)
    
    # Send Email
    background_tasks.add_task(send_otp_email, org_in.email, otp, org_in.name)
    
    return {
        "message": "Verification OTP has been sent on registered email",
        "uuid": str(db_org.uuid),
        "email": db_org.email
    }

@router.post("/resend-otp", status_code=status.HTTP_200_OK)
def resend_otp(
    *,
    db: Session = Depends(deps.get_db),
    resend_in: OrganizationResendOTP,
    background_tasks: BackgroundTasks
):
    """
    Resend OTP to the organization email.
    """
    org = db.query(Organization).filter(Organization.email == resend_in.email).first()
    if not org:
        raise HTTPException(status_code=404, detail="Organization not found")
        
    if org.is_verified:
         raise HTTPException(status_code=400, detail="Organization already verified")

    otp = generate_otp()
    otp_expires = datetime.utcnow() + timedelta(minutes=10)
    
    org.verification_code = otp
    org.verification_code_expires_at = otp_expires
    db.commit()
    
    background_tasks.add_task(send_otp_email, org.email, otp, org.name)
    
    return {"message": "OTP resent successfully"}

@router.post("/verify-otp", status_code=status.HTTP_200_OK)
def verify_otp(
    *,
    db: Session = Depends(deps.get_db),
    verification_in: OrganizationVerifyOTP
):
    """
    Verify the OTP sent to email.
    """
    org = db.query(Organization).filter(Organization.email == verification_in.email).first()
    if not org:
        raise HTTPException(status_code=404, detail="Organization not found")
        
    if org.is_verified:
         return {"message": "Organization already verified"}

    if not org.verification_code or org.verification_code != verification_in.otp:
        raise HTTPException(status_code=400, detail="Invalid OTP")
        
    if org.verification_code_expires_at < datetime.utcnow():
        raise HTTPException(status_code=400, detail="OTP expired")
        
    # Verify
    org.status = OrganizationStatus.ACTIVE 
    org.is_verified = True
    org.verification_code = None
    org.verification_code_expires_at = None
    
    # Generate and Hash Password
    raw_password = generate_password()
    org.hashed_password = security.get_password_hash(raw_password)
    
    # Start trial now
    org.trial_ends_at = datetime.utcnow() + timedelta(days=14)
    
    db.commit()
    
    # Send Welcome Email
    # We send the RAW password so user can login first time.
    # Logic in utils/email.py should handle sending this safely/securely (e.g. over TLS).
    # NOTE: Background task (if we had it in args) or sync here. 
    # Since background_tasks param is missing in verify_otp, we'll run sync or need to add parameter.
    # Let's add background_tasks to function signature first to avoid blocking.
    send_welcome_email(org.email, org.name, raw_password)
    
    return {"message": "Verification successful. Account is active."}

from fastapi import File, UploadFile, Form
from app.models.organization import OrganizationSize
from app.utils.upload import save_upload_file, delete_file

@router.get("/me", response_model=OrganizationSchema)
def get_current_organization_details(
    current_org: Organization = Depends(deps.get_current_org)
):
    """
    Get the details of the currently authenticated organization.
    """
    return current_org

@router.put("/me", response_model=OrganizationSchema)
def update_organization(
    *,
    db: Session = Depends(deps.get_db),
    current_org: Organization = Depends(deps.get_current_org),
    # Form fields matching OrganizationUpdate + logo
    name: str = Form(None),
    organization_size: OrganizationSize = Form(None),
    website: str = Form(None),
    industry: str = Form(None),
    founded_year: int = Form(None),
    gst_number: str = Form(None),
    pan_number: str = Form(None),
    address_line1: str = Form(None),
    address_line2: str = Form(None),
    city: str = Form(None),
    state: str = Form(None),
    country: str = Form(None),
    pincode: str = Form(None),
    logo: UploadFile = File(None)
):
    """
    Update own organization profile (Multipart Form Data). 
    Restricted fields cannot be updated if they are already set.
    """
    org = current_org
    
    # Construct update dict from form data
    update_data = {}
    if name is not None: update_data['name'] = name
    if organization_size is not None: update_data['organization_size'] = organization_size
    if website is not None: update_data['website'] = website
    if industry is not None: update_data['industry'] = industry
    if founded_year is not None: update_data['founded_year'] = founded_year
    if gst_number is not None: update_data['gst_number'] = gst_number
    if pan_number is not None: update_data['pan_number'] = pan_number
    if address_line1 is not None: update_data['address_line1'] = address_line1
    if address_line2 is not None: update_data['address_line2'] = address_line2
    if city is not None: update_data['city'] = city
    if state is not None: update_data['state'] = state
    if country is not None: update_data['country'] = country
    if pincode is not None: update_data['pincode'] = pincode
    
    # Handle Logo Upload
    if logo:
        # Delete old logo if exists
        if org.logo:
            delete_file(org.logo)
            
        # Path structure: {org_uuid}/organization_images/{filename}
        sub_path = f"{org.uuid}/organization_images"
        saved_path = save_upload_file(logo, sub_path)
        update_data['logo'] = saved_path

    # Special checks for "Once set not allowed to change"
    # Note: If client sends None explicitly in JSON it might verify differently, but in Form optional fields are None if missing.
    if "founded_year" in update_data and org.founded_year not in [None, '']:
         raise HTTPException(status_code=400, detail="Founded year cannot be changed once set.")
         
    if "gst_number" in update_data and org.gst_number not in [None, '']:
         raise HTTPException(status_code=400, detail="GST Number cannot be changed once set.")
         
    if "pan_number" in update_data and org.pan_number not in [None, '']:
         raise HTTPException(status_code=400, detail="PAN Number cannot be changed once set.")

    for field, value in update_data.items():
        setattr(org, field, value)

    db.add(org)
    db.commit()
    db.refresh(org)
    return org