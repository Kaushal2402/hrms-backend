from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import func, or_
import typing
from typing import Any, List, Optional
from datetime import datetime, date, timedelta

from app.api import deps
from app.models.employee import EmployeeCertification, Employee
from app.models.organization import Organization
from app.schemas.employee import CertificationListResponse, CertificationSchema, ExpiringCertificationListResponse

router = APIRouter()

@router.get("/expiring", response_model=ExpiringCertificationListResponse)
def get_expiring_certifications(
    days: int = Query(30, description="Number of days to check for expiration"),
    db: Session = Depends(deps.get_db),
    current_org: Organization = Depends(deps.get_current_org),
    current_user: typing.Union[Organization, Employee] = Depends(deps.get_current_user)
):
    """
    Get certifications that are expiring within the specified number of days.
    Includes simplified employee details.
    """
    today = date.today()
    future_date = today + timedelta(days=days)
    
    query = db.query(EmployeeCertification).join(Employee).options(
        joinedload(EmployeeCertification.employee).joinedload(Employee.job_title),
        joinedload(EmployeeCertification.employee).joinedload(Employee.department)
    ).filter(
        EmployeeCertification.expiry_date >= today,
        EmployeeCertification.expiry_date <= future_date,
        EmployeeCertification.is_active == True,
        Employee.organization_id == current_org.id
    )

    # RBAC: Employees can only fetch their own data unless they have administrative permissions (Code 11)
    if not deps.has_permission(db, current_user, "11"):
        query = query.filter(EmployeeCertification.employee_id == current_user.id)
    
    certs = query.all()
    
    return ExpiringCertificationListResponse(
        success=True,
        message=f"Found {len(certs)} expiring certifications",
        data=certs
    )
