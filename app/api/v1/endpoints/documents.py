from typing import List, Optional, Union
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from app.api import deps
from app.models.employee import EmployeeDocument, Employee
from app.schemas.employee import EmployeeDocumentListResponse, DocumentType
from app.models.organization import Organization
from datetime import date, timedelta

router = APIRouter()

@router.get("/expiring", response_model=EmployeeDocumentListResponse)
def get_expiring_documents(
    days: int = Query(30, description="Number of days to check for expiry"),
    document_type: Optional[DocumentType] = None,
    db: Session = Depends(deps.get_db),
    current_org: Organization = Depends(deps.get_current_org),
    current_user: Union[Organization, Employee] = Depends(deps.get_current_user)
):
    """
    Get all documents expiring soon across the organization.
    """
    today = date.today()
    expiry_threshold = today + timedelta(days=days)
    
    query = db.query(EmployeeDocument).filter(
        EmployeeDocument.expiry_date != None,
        EmployeeDocument.expiry_date >= today,
        EmployeeDocument.expiry_date <= expiry_threshold
        # Assuming we should filter by organization?
        # EmployeeDocument -> Employee -> Organization
        # But EmployeeDocument doesn't have organization_id directly.
        # It links to Employee.
    )
    
    # We need to join with Employee to filter by Organization
    from app.models.employee import Employee, JobTitle, Department
    from sqlalchemy.orm import joinedload
    
    query = query.join(Employee).options(
        joinedload(EmployeeDocument.employee).options(
            joinedload(Employee.job_title),
            joinedload(Employee.department)
        )
    ).filter(
        Employee.organization_id == current_org.id,
        Employee.is_deleted == False
    )
    
    if document_type:
        query = query.filter(EmployeeDocument.document_type == document_type)
    
    # RBAC & Ownership Filtering
    is_manager = deps.has_permission(db, current_user, "1")
    if not (isinstance(current_user, Organization) or is_manager):
        # Regular employee can only see their own expiring documents
        query = query.filter(EmployeeDocument.employee_id == current_user.id)
        
    documents = query.order_by(EmployeeDocument.expiry_date.asc()).all()
    
    return EmployeeDocumentListResponse(
        success=True,
        message=f"Found {len(documents)} expiring documents",
        data=documents
    )

@router.get("/", response_model=EmployeeDocumentListResponse)
def get_all_documents(
    document_type: Optional[DocumentType] = None,
    is_verified: Optional[bool] = None,
    db: Session = Depends(deps.get_db),
    current_org: Organization = Depends(deps.get_current_org),
    current_user: Union[Organization, Employee] = Depends(deps.get_current_user)
):
    """
    Get all documents.
    Organizations/Managers see all; Employees see only their own.
    """
    # Use join with Employee to filter by Organization
    from app.models.employee import Employee, JobTitle, Department
    from sqlalchemy.orm import joinedload
    
    query = db.query(EmployeeDocument).join(Employee).options(
        joinedload(EmployeeDocument.employee).options(
            joinedload(Employee.job_title),
            joinedload(Employee.department)
        )
    ).filter(
        Employee.organization_id == current_org.id,
        Employee.is_deleted == False
    )
    
    if document_type:
        query = query.filter(EmployeeDocument.document_type == document_type)
        
    if is_verified is not None:
        query = query.filter(EmployeeDocument.is_verified == is_verified)
        
    # RBAC & Ownership Filtering
    is_manager = deps.has_permission(db, current_user, "1")
    if not (isinstance(current_user, Organization) or is_manager):
        # Regular employee can only see their own documents
        query = query.filter(EmployeeDocument.employee_id == current_user.id)
        
    documents = query.order_by(EmployeeDocument.created_at.desc()).all()
    
    return EmployeeDocumentListResponse(
        success=True,
        message=f"Found {len(documents)} documents",
        data=documents
    )
