import uuid
from typing import List, Optional, Union
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from sqlalchemy import func, or_, and_

from app.api import deps
from app.models.organization import Organization
from app.models.employee import Employee
from app.models.payroll import PayrollReconciliation, PayrollReconciliationIssue, PayrollPeriod
from app.schemas.payroll_reconciliations import (
    PayrollReconciliationCreate, PayrollReconciliationSchema, PayrollReconciliationResponse,
    PayrollReconciliationListResponse, PayrollReconciliationIssueListResponse, IssueResolveUpdate
)
from app.core.permissions import PayrollReconciliationPermissions

router = APIRouter()

def _require_permission(db: Session, current_user: Union[Organization, Employee], code: str, action: str):
    if isinstance(current_user, Organization): return
    if not deps.has_permission(db, current_user, code):
        raise HTTPException(status_code=403, detail=f"Permission denied: {action}")

@router.get("/", response_model=PayrollReconciliationListResponse)
def get_reconciliations(
    db: Session = Depends(deps.get_db),
    current_org: Organization = Depends(deps.get_current_org),
    current_user: Union[Organization, Employee] = Depends(deps.get_current_user),
    page: int = Query(1, ge=1),
    limit: int = Query(10, ge=1, le=100),
    search: Optional[str] = None,
    status: Optional[str] = None,
    sort_by: str = "created_at",
    order: str = "desc"
):
    _require_permission(db, current_user, PayrollReconciliationPermissions.READ, "list")
    query = db.query(PayrollReconciliation).filter(PayrollReconciliation.organization_id == current_org.id)
    
    if search:
        query = query.filter(PayrollReconciliation.reconciliation_number.ilike(f"%{search}%"))
    if status:
        query = query.filter(PayrollReconciliation.status == status)
        
    total_records = query.count()
    items = query.order_by(getattr(PayrollReconciliation, sort_by).desc() if order == "desc" else getattr(PayrollReconciliation, sort_by).asc()).offset((page - 1) * limit).limit(limit).all()
    
    return {"success": True, "message": "Reconciliations retrieved successfully", "data": items, "pagination": {"total_records": total_records, "current_page": page, "total_pages": (total_records + limit - 1) // limit, "page_size": limit}}

@router.post("/", response_model=PayrollReconciliationResponse)
def create_reconciliation(
    item_in: PayrollReconciliationCreate,
    db: Session = Depends(deps.get_db),
    current_org: Organization = Depends(deps.get_current_org),
    current_user: Union[Organization, Employee] = Depends(deps.get_current_user)
):
    _require_permission(db, current_user, PayrollReconciliationPermissions.CREATE, "create")
    
    period = db.query(PayrollPeriod).filter(PayrollPeriod.uuid == item_in.payroll_period_uuid, PayrollPeriod.organization_id == current_org.id).first()
    if not period: raise HTTPException(404, "Period not found")
    
    if db.query(PayrollReconciliation).filter(PayrollReconciliation.payroll_period_id == period.id).first():
        raise HTTPException(400, "Reconciliation already exists for this period")
        
    recon = PayrollReconciliation(
        organization_id=current_org.id,
        payroll_period_id=period.id,
        reconciliation_number=f"REC-{uuid.uuid4().hex[:8].upper()}",
        reconciliation_date=func.now(),
        current_period_gross=period.total_gross_amount,
        current_period_net=period.total_net_amount,
        current_employee_count=period.total_employees,
        status="in_progress"
    )
    db.add(recon)
    db.commit()
    db.refresh(recon)
    return {"success": True, "message": "Reconciliation created successfully", "data": recon}

@router.get("/{recon_uuid}", response_model=PayrollReconciliationResponse)
def get_reconciliation(recon_uuid: uuid.UUID, db: Session = Depends(deps.get_db), current_org: Organization = Depends(deps.get_current_org)):
    recon = db.query(PayrollReconciliation).filter(PayrollReconciliation.uuid == recon_uuid, PayrollReconciliation.organization_id == current_org.id).first()
    if not recon: raise HTTPException(404, "Reconciliation not found")
    return {"success": True, "message": "Details retrieved", "data": recon}

@router.get("/{recon_uuid}/issues", response_model=PayrollReconciliationIssueListResponse)
def get_reconciliation_issues(
    recon_uuid: uuid.UUID,
    db: Session = Depends(deps.get_db),
    current_org: Organization = Depends(deps.get_current_org),
    page: int = Query(1, ge=1),
    limit: int = Query(10, ge=1, le=100)
):
    query = db.query(PayrollReconciliationIssue).join(PayrollReconciliation).filter(
        PayrollReconciliation.uuid == recon_uuid,
        PayrollReconciliation.organization_id == current_org.id
    )
    total = query.count()
    items = query.offset((page - 1) * limit).limit(limit).all()
    return {"success": True, "message": "Issues retrieved", "data": items, "pagination": {"total_records": total, "current_page": page, "total_pages": (total + limit - 1) // limit, "page_size": limit}}

@router.post("/{recon_uuid}/issues/{issue_uuid}/resolve")
def resolve_issue(
    recon_uuid: uuid.UUID,
    issue_uuid: uuid.UUID,
    item_in: IssueResolveUpdate,
    db: Session = Depends(deps.get_db),
    current_org: Organization = Depends(deps.get_current_org)
):
    issue = db.query(PayrollReconciliationIssue).join(PayrollReconciliation).filter(
        PayrollReconciliation.uuid == recon_uuid,
        PayrollReconciliationIssue.uuid == issue_uuid,
        PayrollReconciliation.organization_id == current_org.id
    ).first()
    if not issue: raise HTTPException(404, "Issue not found")
    issue.status = "resolved"
    issue.resolution_notes = item_in.resolution_notes
    db.commit()
    return {"success": True, "message": "Issue resolved successfully"}

@router.post("/{recon_uuid}/approve")
def approve_reconciliation(recon_uuid: uuid.UUID, db: Session = Depends(deps.get_db), current_org: Organization = Depends(deps.get_current_org)):
    recon = db.query(PayrollReconciliation).filter(PayrollReconciliation.uuid == recon_uuid, PayrollReconciliation.organization_id == current_org.id).first()
    if not recon: raise HTTPException(404, "Reconciliation not found")
    
    critical_issues = db.query(PayrollReconciliationIssue).filter(
        PayrollReconciliationIssue.reconciliation_id == recon.id,
        PayrollReconciliationIssue.severity == "critical",
        PayrollReconciliationIssue.status != "resolved"
    ).count()
    
    if critical_issues > 0: raise HTTPException(400, "Cannot approve: unresolved critical issues exist")
    
    recon.status = "approved"
    db.commit()
    return {"success": True, "message": "Reconciliation approved successfully"}