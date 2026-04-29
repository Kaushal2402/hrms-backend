from typing import Generator, Optional, Union
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import jwt, JWTError
from pydantic import ValidationError
from sqlalchemy.orm import Session

from app.core.config import settings

from app.db.session import SessionLocal
from app.models.organization import Organization
from app.models.employee import Employee
from app.models.auth import TokenBlacklist
from app.schemas.auth import TokenPayload

# OAuth2 scheme
oauth2_scheme = OAuth2PasswordBearer(tokenUrl=f"{settings.API_V1_STR}/auth/login")

def get_db() -> Generator:
    try:
        db = SessionLocal()
        yield db
    finally:
        db.close()

def get_current_org(
    db: Session = Depends(get_db),
    token: str = Depends(oauth2_scheme)
) -> Organization:
    try:
        payload = jwt.decode(
            token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM]
        )
        token_data = TokenPayload(**payload)
    except (JWTError, ValidationError):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Could not validate credentials",
        )
    
    # 0. Check if token is blacklisted
    is_blacklisted = db.query(TokenBlacklist).filter(TokenBlacklist.token == token).first()
    if is_blacklisted:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has been revoked/logged out",
        )
    
    # 1. Try to find in Organization
    org = db.query(Organization).filter(Organization.uuid == token_data.sub).first()
    if org:
        return org
    
    # 2. Try to find in Employee
    employee = db.query(Employee).filter(Employee.uuid == token_data.sub).first()
    if employee:
        # Return the organization this employee belongs to
        return employee.organization
    
    raise HTTPException(status_code=404, detail="User or Organization not found")

from app.models.rbac import UserRole, RolePermission, Permission

def get_current_user(
    db: Session = Depends(get_db),
    token: str = Depends(oauth2_scheme)
) -> Union[Organization, Employee]:
    try:
        payload = jwt.decode(
            token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM]
        )
        token_data = TokenPayload(**payload)
    except (JWTError, ValidationError):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Could not validate credentials",
        )
    
    # 0. Check if token is blacklisted
    is_blacklisted = db.query(TokenBlacklist).filter(TokenBlacklist.token == token).first()
    if is_blacklisted:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has been revoked/logged out",
        )
    
    org = db.query(Organization).filter(Organization.uuid == token_data.sub).first()
    if org:
        return org
        
    employee = db.query(Employee).filter(Employee.uuid == token_data.sub).first()
    if employee:
        return employee
        
    raise HTTPException(status_code=404, detail="User not found")

def has_permission(db: Session, current_user: Union[Organization, Employee], permission_code: str) -> bool:
    """
    Check if a user has a specific permission without raising an exception.
    """
    # 1. Organization bypass
    if isinstance(current_user, Organization):
        return True
    
    # 2. Employee permission check
    permission = db.query(Permission).join(
        RolePermission, Permission.id == RolePermission.permission_id
    ).join(
        UserRole, RolePermission.role_id == UserRole.role_id
    ).filter(
        UserRole.user_id == current_user.id,
        UserRole.is_active == True,
        Permission.permission_code == str(permission_code),
        Permission.is_active == True
    ).first()

    return permission is not None

def check_permission(permission_code: str):
    def permission_checker(
        current_user: Union[Organization, Employee] = Depends(get_current_user),
        db: Session = Depends(get_db)
    ):
        # 1. Organization bypass
        if isinstance(current_user, Organization):
            return True
        
        # 2. Employee permission check
        # Look for permission through Employee -> UserRole (active) -> Role (active) -> RolePermission (active) -> Permission (active)
        has_permission = db.query(Permission).join(
            RolePermission, Permission.id == RolePermission.permission_id
        ).join(
            UserRole, RolePermission.role_id == UserRole.role_id
        ).filter(
            UserRole.user_id == current_user.id,
            UserRole.is_active == True,
            Permission.permission_code == str(permission_code),
            Permission.is_active == True
        ).first()

        if not has_permission:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"You do not have permission (code: {permission_code}) to perform this action"
            )
        return True
    return permission_checker
