import uuid
from typing import List, Optional, Union
from datetime import date, datetime
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from sqlalchemy import func, or_
from app.api import deps
from app.models.organization import Organization
from app.models.employee import Employee
from app.models.payroll import ReimbursementCategory, ReimbursementClaim, ReimbursementStatus
from app.schemas.payroll_reimbursements import (
    ReimbursementCategorySchema, ReimbursementCategoryCreate, ReimbursementCategoryListResponse,
    ReimbursementCategoryUpdate,
    ReimbursementClaimSchema, ReimbursementClaimCreate, ReimbursementClaimUpdate,
    ReimbursementApproveUpdate, ReimbursementRejectUpdate, ReimbursementClaimListResponse,
    ReimbursementClaimResponse
)
from app.core.permissions import PayrollReimbursementPermissions

# ----------------------------------------------------------------------------
# ROUTERS DEFINITIONS
# ----------------------------------------------------------------------------
router = APIRouter()
category_router = APIRouter()
employee_router = APIRouter()

# ----------------------------------------------------------------------------
# UTILITY HELPERS
# ----------------------------------------------------------------------------
def _get_org_id(current_user: Union[Organization, Employee]) -> int:
    return current_user.id if isinstance(current_user, Organization) else current_user.organization_id

def _require_permission(db: Session, current_user: Union[Organization, Employee], code: str, action_label: str):
    if isinstance(current_user, Organization):
        return
    if not deps.has_permission(db, current_user, code):
        raise HTTPException(status_code=403, detail=f"Permission denied: {action_label}")

def _require_any_permission(db: Session, current_user: Union[Organization, Employee], codes: List[str], action_label: str):
    if isinstance(current_user, Organization):
        return
    if not any(deps.has_permission(db, current_user, code) for code in codes):
        raise HTTPException(status_code=403, detail=f"Permission denied: {action_label}")

# ----------------------------------------------------------------------------
# 1. REIMBURSEMENT CATEGORIES ENDPOINTS
# ----------------------------------------------------------------------------
@category_router.get("", response_model=ReimbursementCategoryListResponse)
def get_categories(
    is_active: Optional[bool] = None,
    sort_by: str = Query("created_at"),
    order: str = Query("desc"),
    db: Session = Depends(deps.get_db),
    current_user: Union[Organization, Employee] = Depends(deps.get_current_user)
):
    _require_any_permission(
        db, current_user,
        [PayrollReimbursementPermissions.READ, PayrollReimbursementPermissions.CREATE, PayrollReimbursementPermissions.APPROVE],
        "list categories"
    )
    org_id = _get_org_id(current_user)
    query = db.query(ReimbursementCategory).filter(ReimbursementCategory.organization_id == org_id)
    if is_active is not None:
        query = query.filter(ReimbursementCategory.is_active == is_active)
        
    # Safe sorting
    sort_col = getattr(ReimbursementCategory, sort_by, ReimbursementCategory.created_at)
    if order.lower() == "asc":
        query = query.order_by(sort_col.asc())
    else:
        query = query.order_by(sort_col.desc())
        
    items = query.all()
    return {
        "success": True,
        "message": "Categories retrieved successfully",
        "data": items,
        "pagination": {"total_records": len(items)}
    }

@category_router.post("", response_model=ReimbursementCategorySchema, status_code=status.HTTP_201_CREATED)
def create_category(
    item_in: ReimbursementCategoryCreate,
    db: Session = Depends(deps.get_db),
    current_user: Union[Organization, Employee] = Depends(deps.get_current_user)
):
    _require_permission(db, current_user, PayrollReimbursementPermissions.CREATE, "create category")
    org_id = _get_org_id(current_user)
    
    # Check if category code already exists
    existing = db.query(ReimbursementCategory).filter(
        ReimbursementCategory.organization_id == org_id,
        ReimbursementCategory.category_code == item_in.category_code
    ).first()
    if existing:
        raise HTTPException(status_code=400, detail="Category code already exists")

    item = ReimbursementCategory(organization_id=org_id, **item_in.model_dump())
    db.add(item)
    db.commit()
    db.refresh(item)
    return item

@category_router.get("/lookup", response_model=ReimbursementCategoryListResponse)
def lookup_categories(
    is_active: Optional[bool] = True,
    db: Session = Depends(deps.get_db),
    current_user: Union[Organization, Employee] = Depends(deps.get_current_user)
):
    org_id = _get_org_id(current_user)
    query = db.query(ReimbursementCategory).filter(
        ReimbursementCategory.organization_id == org_id
    )
    if is_active is not None:
        query = query.filter(ReimbursementCategory.is_active == is_active)
        
    items = query.order_by(ReimbursementCategory.category_name.asc()).all()
    
    return {
        "success": True,
        "message": "Categories lookup successful",
        "data": items,
        "pagination": {
            "total_records": len(items),
            "current_page": 1,
            "total_pages": 1,
            "page_size": len(items)
        }
    }

@category_router.get("/{category_uuid}", response_model=ReimbursementCategorySchema)
def get_category(
    category_uuid: uuid.UUID,
    db: Session = Depends(deps.get_db),
    current_user: Union[Organization, Employee] = Depends(deps.get_current_user)
):
    _require_any_permission(
        db, current_user,
        [PayrollReimbursementPermissions.READ, PayrollReimbursementPermissions.CREATE, PayrollReimbursementPermissions.APPROVE],
        "view category details"
    )
    org_id = _get_org_id(current_user)
    cat = db.query(ReimbursementCategory).filter(
        ReimbursementCategory.uuid == category_uuid,
        ReimbursementCategory.organization_id == org_id
    ).first()
    if not cat:
        raise HTTPException(status_code=404, detail="Category not found")
    return cat

@category_router.put("/{category_uuid}", response_model=ReimbursementCategorySchema)
def update_category(
    category_uuid: uuid.UUID,
    item_in: ReimbursementCategoryUpdate,
    db: Session = Depends(deps.get_db),
    current_user: Union[Organization, Employee] = Depends(deps.get_current_user)
):
    _require_permission(db, current_user, PayrollReimbursementPermissions.CREATE, "update category")
    org_id = _get_org_id(current_user)
    cat = db.query(ReimbursementCategory).filter(
        ReimbursementCategory.uuid == category_uuid,
        ReimbursementCategory.organization_id == org_id
    ).first()
    if not cat:
        raise HTTPException(status_code=404, detail="Category not found")
        
    for k, v in item_in.model_dump(exclude_unset=True).items():
        setattr(cat, k, v)
    db.commit()
    db.refresh(cat)
    return cat

# ----------------------------------------------------------------------------
# 2. REIMBURSEMENT CLAIMS ENDPOINTS
# ----------------------------------------------------------------------------
@router.get("", response_model=ReimbursementClaimListResponse)
def get_claims(
    employee_uuid: Optional[uuid.UUID] = None,
    status: Optional[ReimbursementStatus] = None,
    category_uuid: Optional[uuid.UUID] = None,
    from_date: Optional[date] = None,
    to_date: Optional[date] = None,
    search: Optional[str] = None,
    page: int = Query(1, ge=1),
    limit: int = Query(10, ge=1, le=100),
    sort_by: str = Query("created_at"),
    order: str = Query("desc"),
    db: Session = Depends(deps.get_db),
    current_user: Union[Organization, Employee] = Depends(deps.get_current_user)
):
    _require_any_permission(
        db, current_user,
        [PayrollReimbursementPermissions.READ, PayrollReimbursementPermissions.APPROVE],
        "list claims"
    )
    org_id = _get_org_id(current_user)
    query = db.query(ReimbursementClaim).filter(ReimbursementClaim.organization_id == org_id)
    
    # Non-admin users can ONLY see their own claims
    is_admin = isinstance(current_user, Organization) or deps.has_permission(db, current_user, PayrollReimbursementPermissions.APPROVE) or deps.has_permission(db, current_user, PayrollReimbursementPermissions.READ)
    
    if not is_admin:
        query = query.filter(ReimbursementClaim.employee_id == current_user.id)
    elif employee_uuid:
        emp = db.query(Employee).filter(Employee.uuid == employee_uuid, Employee.organization_id == org_id).first()
        if emp:
            query = query.filter(ReimbursementClaim.employee_id == emp.id)
            
    if status:
        query = query.filter(ReimbursementClaim.status == status)
        
    if category_uuid:
        cat = db.query(ReimbursementCategory).filter(ReimbursementCategory.uuid == category_uuid, ReimbursementCategory.organization_id == org_id).first()
        if cat:
            query = query.filter(ReimbursementClaim.category_id == cat.id)
            
    if from_date:
        query = query.filter(ReimbursementClaim.expense_date >= from_date)
    if to_date:
        query = query.filter(ReimbursementClaim.expense_date <= to_date)
        
    if search:
        query = query.filter(
            or_(
                ReimbursementClaim.claim_number.ilike(f"%{search}%"),
                ReimbursementClaim.description.ilike(f"%{search}%"),
                ReimbursementClaim.merchant_name.ilike(f"%{search}%")
            )
        )
        
    total = query.count()
    
    # Safe sorting
    if sort_by == "category":
        query = query.join(ReimbursementClaim.category)
        sort_col = ReimbursementCategory.category_name
    else:
        sort_col = getattr(ReimbursementClaim, sort_by, None)
        if sort_col is None or not hasattr(sort_col, "asc"):
            sort_col = ReimbursementClaim.created_at

    if order.lower() == "asc":
        query = query.order_by(sort_col.asc())
    else:
        query = query.order_by(sort_col.desc())
        
    items = query.offset((page - 1) * limit).limit(limit).all()
    
    return {
        "success": True,
        "message": "Claims retrieved successfully",
        "data": items,
        "pagination": {
            "total_records": total,
            "current_page": page,
            "total_pages": (total + limit - 1) // limit,
            "page_size": limit
        }
    }

@router.get("/pending-approvals", response_model=ReimbursementClaimListResponse)
def get_pending_approvals(
    approver_uuid: Optional[uuid.UUID] = None,
    page: int = Query(1, ge=1),
    limit: int = Query(10, ge=1, le=100),
    sort_by: str = Query("created_at"),
    order: str = Query("desc"),
    db: Session = Depends(deps.get_db),
    current_user: Union[Organization, Employee] = Depends(deps.get_current_user)
):
    _require_any_permission(
        db, current_user,
        [PayrollReimbursementPermissions.READ, PayrollReimbursementPermissions.APPROVE],
        "view pending approvals"
    )
    org_id = _get_org_id(current_user)
    
    query = db.query(ReimbursementClaim).filter(
        ReimbursementClaim.organization_id == org_id,
        ReimbursementClaim.status == ReimbursementStatus.SUBMITTED
    )
    
    if approver_uuid:
        approver = db.query(Employee).filter(Employee.uuid == approver_uuid, Employee.organization_id == org_id).first()
        if approver:
            query = query.filter(ReimbursementClaim.approver_id == approver.id)
            
    total = query.count()
    
    # Safe sorting
    if sort_by == "category":
        query = query.join(ReimbursementClaim.category)
        sort_col = ReimbursementCategory.category_name
    else:
        sort_col = getattr(ReimbursementClaim, sort_by, None)
        if sort_col is None or not hasattr(sort_col, "asc"):
            sort_col = ReimbursementClaim.created_at

    if order.lower() == "asc":
        query = query.order_by(sort_col.asc())
    else:
        query = query.order_by(sort_col.desc())
        
    items = query.offset((page - 1) * limit).limit(limit).all()
    
    return {
        "success": True,
        "message": "Pending approvals retrieved successfully",
        "data": items,
        "pagination": {
            "total_records": total,
            "current_page": page,
            "total_pages": (total + limit - 1) // limit,
            "page_size": limit
        }
    }

@router.post("", response_model=ReimbursementClaimResponse, status_code=status.HTTP_201_CREATED)
def create_claim(
    item_in: ReimbursementClaimCreate,
    db: Session = Depends(deps.get_db),
    current_user: Union[Organization, Employee] = Depends(deps.get_current_user)
):
    if isinstance(current_user, Organization):
        raise HTTPException(status_code=400, detail="Organizations cannot submit reimbursement claims")
        
    org_id = _get_org_id(current_user)
    
    # Verify category
    cat = db.query(ReimbursementCategory).filter(
        ReimbursementCategory.uuid == item_in.category_uuid,
        ReimbursementCategory.organization_id == org_id
    ).first()
    if not cat:
        raise HTTPException(status_code=404, detail="Category not found")
        
    # Thread-safe robust claim number generation
    emp_code = current_user.employee_code or "EMP"
    claim_num = f"RC-{emp_code}-{datetime.utcnow().strftime('%Y%m%d%H%M%S')}-{uuid.uuid4().hex[:6].upper()}"
    
    claim = ReimbursementClaim(
        organization_id=org_id,
        employee_id=current_user.id,
        category_id=cat.id,
        claim_number=claim_num,
        status=ReimbursementStatus.DRAFT,
        **item_in.model_dump(exclude={'category_uuid'})
    )
    db.add(claim)
    db.commit()
    db.refresh(claim)
    return {"success": True, "message": "Claim created successfully as draft", "data": claim}

@router.get("/{claim_uuid}", response_model=ReimbursementClaimResponse)
def get_claim(
    claim_uuid: uuid.UUID,
    db: Session = Depends(deps.get_db),
    current_user: Union[Organization, Employee] = Depends(deps.get_current_user)
):
    org_id = _get_org_id(current_user)
    claim = db.query(ReimbursementClaim).filter(
        ReimbursementClaim.uuid == claim_uuid,
        ReimbursementClaim.organization_id == org_id
    ).first()
    if not claim:
        raise HTTPException(status_code=404, detail="Claim not found")
        
    # Access enforcement
    is_admin = isinstance(current_user, Organization) or deps.has_permission(db, current_user, PayrollReimbursementPermissions.APPROVE) or deps.has_permission(db, current_user, PayrollReimbursementPermissions.READ)
    if not is_admin and claim.employee_id != current_user.id:
        raise HTTPException(status_code=403, detail="Access denied")
        
    return {"success": True, "message": "Claim retrieved successfully", "data": claim}

@router.put("/{claim_uuid}", response_model=ReimbursementClaimResponse)
def update_claim(
    claim_uuid: uuid.UUID,
    item_in: ReimbursementClaimUpdate,
    db: Session = Depends(deps.get_db),
    current_user: Union[Organization, Employee] = Depends(deps.get_current_user)
):
    org_id = _get_org_id(current_user)
    claim = db.query(ReimbursementClaim).filter(
        ReimbursementClaim.uuid == claim_uuid,
        ReimbursementClaim.organization_id == org_id
    ).first()
    if not claim:
        raise HTTPException(status_code=404, detail="Claim not found")
        
    if claim.employee_id != current_user.id:
        raise HTTPException(status_code=403, detail="Only the claim owner can update it")
        
    if claim.status != ReimbursementStatus.DRAFT:
        raise HTTPException(status_code=400, detail="Only DRAFT claims can be updated")
        
    for k, v in item_in.model_dump(exclude_unset=True).items():
        setattr(claim, k, v)
        
    db.commit()
    db.refresh(claim)
    return {"success": True, "message": "Claim updated successfully", "data": claim}

@router.post("/{claim_uuid}/submit", response_model=ReimbursementClaimResponse)
def submit_claim(
    claim_uuid: uuid.UUID,
    db: Session = Depends(deps.get_db),
    current_user: Union[Organization, Employee] = Depends(deps.get_current_user)
):
    org_id = _get_org_id(current_user)
    claim = db.query(ReimbursementClaim).filter(
        ReimbursementClaim.uuid == claim_uuid,
        ReimbursementClaim.organization_id == org_id
    ).first()
    if not claim:
        raise HTTPException(status_code=404, detail="Claim not found")
        
    if claim.employee_id != current_user.id:
        raise HTTPException(status_code=403, detail="Only the claim owner can submit it")
        
    if claim.status != ReimbursementStatus.DRAFT:
        raise HTTPException(status_code=400, detail="Only DRAFT claims can be submitted")
        
    claim.status = ReimbursementStatus.SUBMITTED
    claim.submitted_at = datetime.utcnow()
    db.commit()
    db.refresh(claim)
    return {"success": True, "message": "Claim submitted for approval successfully", "data": claim}

@router.post("/{claim_uuid}/approve", response_model=ReimbursementClaimResponse)
def approve_claim(
    claim_uuid: uuid.UUID,
    item_in: ReimbursementApproveUpdate,
    db: Session = Depends(deps.get_db),
    current_user: Union[Organization, Employee] = Depends(deps.get_current_user)
):
    _require_permission(db, current_user, PayrollReimbursementPermissions.APPROVE, "approve claim")
    org_id = _get_org_id(current_user)
    
    claim = db.query(ReimbursementClaim).filter(
        ReimbursementClaim.uuid == claim_uuid,
        ReimbursementClaim.organization_id == org_id
    ).first()
    if not claim:
        raise HTTPException(status_code=404, detail="Claim not found")
        
    if claim.status != ReimbursementStatus.SUBMITTED:
        raise HTTPException(status_code=400, detail="Only SUBMITTED claims can be approved")

    approved = item_in.approved_amount if item_in.approved_amount is not None else claim.claimed_amount
    if approved <= 0:
        raise HTTPException(status_code=400, detail="Approved amount must be greater than zero")
    if approved > claim.claimed_amount:
        raise HTTPException(status_code=400, detail=f"Approved amount cannot exceed claimed amount of {claim.claimed_amount}")

    claim.status = ReimbursementStatus.APPROVED
    claim.approved_amount = approved
    claim.approver_comments = item_in.approver_comments
    claim.approved_at = datetime.utcnow()
    if not isinstance(current_user, Organization):
        claim.approver_id = current_user.id
        
    db.commit()
    db.refresh(claim)
    return {"success": True, "message": "Claim approved successfully", "data": claim}

@router.post("/{claim_uuid}/reject", response_model=ReimbursementClaimResponse)
def reject_claim(
    claim_uuid: uuid.UUID,
    item_in: ReimbursementRejectUpdate,
    db: Session = Depends(deps.get_db),
    current_user: Union[Organization, Employee] = Depends(deps.get_current_user)
):
    _require_permission(db, current_user, PayrollReimbursementPermissions.APPROVE, "reject claim")
    org_id = _get_org_id(current_user)
    
    claim = db.query(ReimbursementClaim).filter(
        ReimbursementClaim.uuid == claim_uuid,
        ReimbursementClaim.organization_id == org_id
    ).first()
    if not claim:
        raise HTTPException(status_code=404, detail="Claim not found")
        
    if claim.status != ReimbursementStatus.SUBMITTED:
        raise HTTPException(status_code=400, detail="Only SUBMITTED claims can be rejected")
        
    claim.status = ReimbursementStatus.REJECTED
    claim.rejection_reason = item_in.rejection_reason
    claim.rejected_at = datetime.utcnow()
    if not isinstance(current_user, Organization):
        claim.approver_id = current_user.id
        
    db.commit()
    db.refresh(claim)
    return {"success": True, "message": "Claim rejected successfully", "data": claim}

# ----------------------------------------------------------------------------
# 3. EMPLOYEE SPECIFIC ENDPOINTS
# ----------------------------------------------------------------------------
@employee_router.get("/{employee_uuid}/reimbursements", response_model=ReimbursementClaimListResponse)
def get_employee_reimbursements(
    employee_uuid: uuid.UUID,
    status: Optional[ReimbursementStatus] = None,
    financial_year: Optional[str] = None,
    search: Optional[str] = None,
    page: int = Query(1, ge=1),
    limit: int = Query(10, ge=1, le=100),
    sort_by: str = Query("created_at"),
    order: str = Query("desc"),
    db: Session = Depends(deps.get_db),
    current_user: Union[Organization, Employee] = Depends(deps.get_current_user)
):
    org_id = _get_org_id(current_user)
    
    # Verify Employee exists
    emp = db.query(Employee).filter(Employee.uuid == employee_uuid, Employee.organization_id == org_id).first()
    if not emp:
        raise HTTPException(status_code=404, detail="Employee not found")
        
    # Access enforcement: Employees can ONLY view their own records
    is_admin = isinstance(current_user, Organization) or deps.has_permission(db, current_user, PayrollReimbursementPermissions.APPROVE) or deps.has_permission(db, current_user, PayrollReimbursementPermissions.READ)
    if not is_admin and emp.id != current_user.id:
        raise HTTPException(status_code=403, detail="Access denied")
        
    query = db.query(ReimbursementClaim).filter(
        ReimbursementClaim.employee_id == emp.id,
        ReimbursementClaim.organization_id == org_id
    )
    
    if status:
        query = query.filter(ReimbursementClaim.status == status)
    
    if search:
        search_term = f"%{search.strip()}%"
        query = query.filter(
            or_(
                ReimbursementClaim.claim_number.ilike(search_term),
                ReimbursementClaim.description.ilike(search_term),
                ReimbursementClaim.merchant_name.ilike(search_term)
            )
        )
        
    if financial_year:
        # Expect financial_year format like '2025-2026' or just a year '2026'
        try:
            if "-" in financial_year:
                start_yr, end_yr = financial_year.split("-")
                start_date = date(int(start_yr), 4, 1)
                end_date = date(int(end_yr), 3, 31)
            else:
                start_date = date(int(financial_year), 4, 1)
                end_date = date(int(financial_year) + 1, 3, 31)
            query = query.filter(
                ReimbursementClaim.expense_date >= start_date,
                ReimbursementClaim.expense_date <= end_date
            )
        except Exception:
            raise HTTPException(status_code=400, detail="Invalid financial year format. Use YYYY or YYYY-YYYY")
            
    total = query.count()
    
    # Safe sorting
    if sort_by == "category":
        query = query.join(ReimbursementClaim.category)
        sort_col = ReimbursementCategory.category_name
    else:
        sort_col = getattr(ReimbursementClaim, sort_by, None)
        if sort_col is None or not hasattr(sort_col, "asc"):
            sort_col = ReimbursementClaim.created_at

    if order.lower() == "asc":
        query = query.order_by(sort_col.asc())
    else:
        query = query.order_by(sort_col.desc())
        
    items = query.offset((page - 1) * limit).limit(limit).all()
    
    # Calculate summary details
    from sqlalchemy import func
    from decimal import Decimal
    
    total_claims = db.query(ReimbursementClaim).filter(
        ReimbursementClaim.employee_id == emp.id,
        ReimbursementClaim.organization_id == org_id
    ).count()

    pending_approval_claims = db.query(ReimbursementClaim).filter(
        ReimbursementClaim.employee_id == emp.id,
        ReimbursementClaim.organization_id == org_id,
        ReimbursementClaim.status == ReimbursementStatus.SUBMITTED
    ).count()

    approved_amount_res = db.query(func.coalesce(func.sum(ReimbursementClaim.approved_amount), 0)).filter(
        ReimbursementClaim.employee_id == emp.id,
        ReimbursementClaim.organization_id == org_id,
        ReimbursementClaim.status.in_([ReimbursementStatus.APPROVED, ReimbursementStatus.PAID])
    ).scalar()
    approved_amount = Decimal(str(approved_amount_res or 0))

    rejected_claims = db.query(ReimbursementClaim).filter(
        ReimbursementClaim.employee_id == emp.id,
        ReimbursementClaim.organization_id == org_id,
        ReimbursementClaim.status == ReimbursementStatus.REJECTED
    ).count()

    summary_data = {
        "total_claims": total_claims,
        "pending_approval_claims": pending_approval_claims,
        "approved_amount": approved_amount,
        "rejected_claims": rejected_claims
    }

    return {
        "success": True,
        "message": "Employee reimbursements retrieved successfully",
        "data": items,
        "summary": summary_data,
        "pagination": {
            "total_records": total,
            "current_page": page,
            "total_pages": (total + limit - 1) // limit,
            "page_size": limit
        }
    }