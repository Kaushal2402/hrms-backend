from datetime import datetime, timedelta
from typing import Any
from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session

from app.api import deps
from app.core import security
from app.core.config import settings
from app.models.organization import Organization, OrganizationStatus
from app.models.employee import Employee, EmploymentStatus
from app.models.auth import TokenBlacklist
from app.models.rbac import UserRole, RolePermission, Permission
from jose import jwt
from app.schemas.auth import Token, Login, ForgotPassword, ResetPassword, SetPassword
from app.schemas.organization import Organization as OrganizationSchema
from app.schemas.employee import EmployeeSchema
from app.schemas.rbac import Permission as PermissionSchema
from app.utils.email import send_reset_password_email
from app.utils.onboarding import get_onboarding_progress

router = APIRouter()

@router.post("/login", response_model=Any)
def login(
    login_in: Login,
    db: Session = Depends(deps.get_db)
):
    """
    OAuth2 compatible token login, get an access token for future requests.
    Returns Access Token + User Data (Organization or Employee).
    """
    # 1. Try to find in Organization
    user_type = "organization"
    user_obj = db.query(Organization).filter(Organization.email == login_in.email).first()
    
    # 2. If not found in Org, try Employee (Work Email first, then Personal Email)
    if not user_obj:
        user_type = "employee"
        user_obj = db.query(Employee).filter(
            (Employee.work_email == login_in.email) | (Employee.personal_email == login_in.email)
        ).first()

    if not user_obj:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Incorrect email or password"
        )
        
    if not user_obj.hashed_password:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Password not set for this account"
        )

    if not security.verify_password(login_in.password, user_obj.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Incorrect email or password"
        )
        
    # Status checks
    if user_type == "organization":
        if user_obj.status in [OrganizationStatus.SUSPENDED, OrganizationStatus.INACTIVE]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail=f"Account is {user_obj.status}"
            )
        if not user_obj.is_verified:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail="Account not verified"
            )
    else: # Employee checks
        if user_obj.employment_status != EmploymentStatus.ACTIVE:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail=f"Employee account is {user_obj.employment_status}"
            )
        if not user_obj.is_active:
             raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail="Employee account is inactive"
            )

    # Create Token
    access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = security.create_access_token(
        subject=user_obj.uuid, expires_delta=access_token_expires
    )
    
    # Return Response
    response_data = {
        "access_token": access_token,
        "token_type": "bearer",
        "user_type": user_type,
        "is_organization": user_type == "organization"
    }
    
    if user_type == "organization":
        response_data["organization"] = OrganizationSchema.model_validate(user_obj)
        response_data["onboarding_progress"] = get_onboarding_progress(db, user_obj.id)
    else:
        response_data["employee"] = EmployeeSchema.model_validate(user_obj)
        # Fetch permissions
        permissions = db.query(Permission).join(
            RolePermission, Permission.id == RolePermission.permission_id
        ).join(
            UserRole, RolePermission.role_id == UserRole.role_id
        ).filter(
            UserRole.user_id == user_obj.id,
            UserRole.is_active == True,
            Permission.is_active == True
        ).all()
        response_data["permissions"] = [PermissionSchema.model_validate(p) for p in permissions]
        
    return response_data

@router.post("/forgot-password")
def forgot_password(
    forgot_in: ForgotPassword,
    background_tasks: BackgroundTasks,
    db: Session = Depends(deps.get_db)
):
    """
    Password Recovery. Sends a reset link to the registered email.
    """
    # 1. Try Organization
    user_obj = db.query(Organization).filter(Organization.email == forgot_in.email).first()
    
    # 2. Try Employee
    if not user_obj:
        user_obj = db.query(Employee).filter(
            (Employee.work_email == forgot_in.email) | (Employee.personal_email == forgot_in.email)
        ).first()

    if not user_obj:
        raise HTTPException(status_code=404, detail="Email not found")
        
    # Generate Reset Token
    reset_token = security.create_access_token(subject=user_obj.uuid, expires_delta=timedelta(hours=1))
    
    user_obj.reset_password_token = reset_token
    user_obj.reset_password_token_expires_at = datetime.utcnow() + timedelta(hours=1)
    db.commit()
    
    # Send Email
    email = user_obj.email if hasattr(user_obj, 'email') else user_obj.work_email
    background_tasks.add_task(send_reset_password_email, email, reset_token)
    
    return {"message": "Password reset link sent to your email"}

@router.post("/reset-password")
def reset_password(
    reset_in: ResetPassword,
    db: Session = Depends(deps.get_db)
):
    """
    Reset password using the token received in email.
    """
    # Try Organization
    user_obj = db.query(Organization).filter(Organization.reset_password_token == reset_in.token).first()
    
    # Try Employee
    if not user_obj:
        user_obj = db.query(Employee).filter(Employee.reset_password_token == reset_in.token).first()
    
    if not user_obj:
        raise HTTPException(status_code=400, detail="Invalid token")
        
    if user_obj.reset_password_token_expires_at < datetime.utcnow():
         raise HTTPException(status_code=400, detail="Token expired")
         
    # Set new password
    user_obj.hashed_password = security.get_password_hash(reset_in.new_password)
    user_obj.reset_password_token = None
    user_obj.reset_password_token_expires_at = None
    db.commit()
    
    return {"message": "Password updated successfully"}

@router.post("/set-password")
def set_password(
    set_in: SetPassword,
    db: Session = Depends(deps.get_db)
):
    """
    Set initial password for a new employee (or anyone with a token). 
    Functionally similar to reset-password but dedicated to the setup flow.
    """
    user_obj = db.query(Organization).filter(Organization.reset_password_token == set_in.token).first()
    if not user_obj:
        user_obj = db.query(Employee).filter(Employee.reset_password_token == set_in.token).first()
    
    if not user_obj:
        raise HTTPException(status_code=400, detail="Invalid token")
        
    if user_obj.reset_password_token_expires_at < datetime.utcnow():
         raise HTTPException(status_code=400, detail="Token expired")
         
    # Set new password
    user_obj.hashed_password = security.get_password_hash(set_in.new_password)
    user_obj.reset_password_token = None
    user_obj.reset_password_token_expires_at = None
    db.commit()
    
    return {"message": "Password set successfully. You can now login."}

@router.post("/logout")
def logout(
    current_user: Any = Depends(deps.get_current_user),
    token: str = Depends(deps.oauth2_scheme),
    db: Session = Depends(deps.get_db)
):
    """
    Logout the user by invalidating their JWT token.
    The token is added to the token_blacklist table to prevent future use.
    """
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM], options={"verify_exp": False})
        expire_timestamp = payload.get("exp")
        if expire_timestamp:
            expires_at = datetime.utcfromtimestamp(expire_timestamp)
        else:
            expires_at = datetime.utcnow() + timedelta(days=1) # Fallback
            
        blacklisted_token = TokenBlacklist(
            token=token,
            expires_at=expires_at
        )
        db.add(blacklisted_token)
        db.commit()
    except Exception as e:
        # If token is invalid or already expired, we can just ignore or raise
        pass

    return {"message": "Successfully logged out"}
