from typing import List, Optional, Union
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from app.api import deps
from app.models.employee import CostCenter
from app.schemas.cost_center import (
    CostCenterSchema,
    CostCenterCreate,
    CostCenterUpdate,
    CostCenterResponse,
    CostCenterListResponse,
    CostCenterDetailResponse,
    CostCenterDetailSchema,
    CostCenterDeleteResponse
)
from app.models.organization import Organization
from app.models.employee import CostCenter, Employee
from datetime import datetime
import uuid

router = APIRouter()

@router.get("/", response_model=CostCenterListResponse)
def list_cost_centers(
    db: Session = Depends(deps.get_db),
    current_org: Organization = Depends(deps.get_current_org),
    current_user: Union[Organization, Employee] = Depends(deps.get_current_user),
    is_active: Optional[bool] = Query(None, description="Filter by active status"),
    search: Optional[str] = Query(None, description="Search by cost_center_name"),
    page: Optional[int] = Query(None, ge=1, description="Page number"),
    limit: int = Query(10, ge=1, description="Items per page"),
    sort_by: Optional[str] = Query("Recent", description="Sort by field: cost_center_code, cost_center_name, is_active, Recent, Oldest"),
    sort_order: str = Query("desc", description="Sort order: asc, desc"),
    authorized: bool = Depends(deps.check_permission("17"))
):
    """
    List all cost centers for the authenticated organization.
    """
    query = db.query(CostCenter).filter(
        CostCenter.organization_id == current_org.id,
        CostCenter.is_deleted == False
    )
    
    if is_active is not None:
        query = query.filter(CostCenter.is_active == is_active)
        
    if search:
        search_term = f"%{search}%"
        query = query.filter(CostCenter.cost_center_name.ilike(search_term))
        
    # Sorting logic
    sort_mapping = {
        "cost_center_code": CostCenter.cost_center_code,
        "cost_center_name": CostCenter.cost_center_name,
        "is_active": CostCenter.is_active,
        "Recent": CostCenter.id,
        "Oldest": CostCenter.id
    }
    
    # Default to ID if sort_by is not in mapping
    sort_field = sort_mapping.get(sort_by, CostCenter.id)
    
    effective_order = sort_order.lower()
    if sort_by == "Oldest" and sort_order == "desc":
         effective_order = "desc"
    elif sort_by == "Oldest":
         effective_order = "asc"

    if effective_order == "asc":
        query = query.order_by(sort_field.asc())
    else:
        query = query.order_by(sort_field.desc())
        
    total_records = query.count()
    
    pagination_data = None
    if page is not None:
        total_pages = (total_records + limit - 1) // limit
        skip = (page - 1) * limit
        cost_centers = query.offset(skip).limit(limit).all()
        pagination_data = {
            "total_records": total_records,
            "current_page": page,
            "total_pages": total_pages,
            "page_size": limit
        }
    else:
        cost_centers = query.all()
        pagination_data = {
            "total_records": total_records,
            "current_page": 1,
            "total_pages": 1,
            "page_size": total_records if total_records > 0 else 0
        }
        
    if not cost_centers:
        return CostCenterListResponse(
            success=False,
            message="No cost centers found"
        )
        
    return CostCenterListResponse(
        success=True,
        message="Cost centers retrieved successfully",
        data=cost_centers,
        pagination=pagination_data
    )

@router.get("/lookup")
def lookup_cost_centers(
    db: Session = Depends(deps.get_db),
    current_org: Organization = Depends(deps.get_current_org),
    search: Optional[str] = Query(None, description="Search by cost_center_name or code"),
    limit: int = Query(100, ge=1, description="Limit lookup results")
):
    """
    Lite lookup endpoint for cost centers (UUID, Cost Center Name).
    Accessible to all authenticated users for filters/dropdowns.
    """
    query = db.query(CostCenter).filter(
        CostCenter.organization_id == current_org.id,
        CostCenter.is_active == True,
        CostCenter.is_deleted == False
    )
    
    if search:
        search_term = f"%{search}%"
        query = query.filter(
            (CostCenter.cost_center_name.ilike(search_term)) |
            (CostCenter.cost_center_code.ilike(search_term))
        )
        
    cost_centers = query.order_by(CostCenter.cost_center_name.asc()).limit(limit).all()
    
    return {
        "success": True,
        "data": [{"uuid": cc.uuid, "cost_center_name": cc.cost_center_name} for cc in cost_centers]
    }

@router.post("/", response_model=CostCenterResponse)
def create_cost_center(
    cost_center_in: CostCenterCreate,
    db: Session = Depends(deps.get_db),
    current_org: Organization = Depends(deps.get_current_org),
    authorized: bool = Depends(deps.check_permission("18"))
):
    """
    Create a new cost center.
    """
    # Check if cost center with same code exists
    existing_cc = db.query(CostCenter).filter(
        CostCenter.organization_id == current_org.id,
        CostCenter.cost_center_code == cost_center_in.cost_center_code
    ).first()
    
    if existing_cc:
        raise HTTPException(
            status_code=400,
            detail=f"Cost center with code '{cost_center_in.cost_center_code}' already exists."
        )
        
    db_obj = CostCenter(
        **cost_center_in.model_dump(),
        organization_id=current_org.id
    )
    db.add(db_obj)
    try:
        db.commit()
        db.refresh(db_obj)
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e))
        
    return CostCenterResponse(
        success=True,
        message="Cost center created successfully",
        data=db_obj
    )



@router.get("/{cost_center_uuid}", response_model=CostCenterDetailResponse)
def get_cost_center(
    cost_center_uuid: uuid.UUID,
    db: Session = Depends(deps.get_db),
    current_org: Organization = Depends(deps.get_current_org),
    authorized: bool = Depends(deps.check_permission("17"))
):
    """
    Get cost center details.
    """
    cost_center = db.query(CostCenter).filter(
        CostCenter.uuid == cost_center_uuid,
        CostCenter.organization_id == current_org.id,
        CostCenter.is_deleted == False
    ).first()
    
    if not cost_center:
        raise HTTPException(status_code=404, detail="Cost center not found")
        
    # Count employees with this cost center
    employee_count = db.query(Employee).filter(
        Employee.cost_center_id == cost_center.id,
        Employee.is_deleted == False
    ).count()
    
    data = CostCenterDetailSchema.model_validate(cost_center)
    data.employee_count = employee_count
    
    return CostCenterDetailResponse(
        success=True,
        message="Cost center retrieved successfully",
        data=data
    )

@router.put("/{cost_center_uuid}", response_model=CostCenterResponse)
def update_cost_center(
    cost_center_uuid: uuid.UUID,
    cost_center_in: CostCenterUpdate,
    db: Session = Depends(deps.get_db),
    current_org: Organization = Depends(deps.get_current_org),
    authorized: bool = Depends(deps.check_permission("19"))
):
    """
    Update a cost center.
    """
    cost_center = db.query(CostCenter).filter(
        CostCenter.uuid == cost_center_uuid,
        CostCenter.organization_id == current_org.id,
        CostCenter.is_deleted == False
    ).first()
    
    if not cost_center:
        raise HTTPException(status_code=404, detail="Cost center not found")
        
    # Check duplicate code if being updated
    if cost_center_in.cost_center_code and cost_center_in.cost_center_code != cost_center.cost_center_code:
        existing_cc = db.query(CostCenter).filter(
            CostCenter.organization_id == current_org.id,
            CostCenter.cost_center_code == cost_center_in.cost_center_code
        ).first()
        if existing_cc:
            raise HTTPException(
                status_code=400,
                detail=f"Cost center with code '{cost_center_in.cost_center_code}' already exists."
            )
            
    update_data = cost_center_in.model_dump(exclude_unset=True)
    
    for field, value in update_data.items():
        setattr(cost_center, field, value)
        
    db.add(cost_center)
    try:
        db.commit()
        db.refresh(cost_center)
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e))
        
    return CostCenterResponse(
        success=True,
        message="Cost center updated successfully",
        data=cost_center
    )

@router.delete("/{cost_center_uuid}", response_model=CostCenterDeleteResponse)
def delete_cost_center(
    cost_center_uuid: uuid.UUID,
    db: Session = Depends(deps.get_db),
    current_org: Organization = Depends(deps.get_current_org),
    authorized: bool = Depends(deps.check_permission("20"))
):
    """
    Delete a cost center (soft delete).
    """
    cost_center = db.query(CostCenter).filter(
        CostCenter.uuid == cost_center_uuid,
        CostCenter.organization_id == current_org.id,
        CostCenter.is_deleted == False
    ).first()
    
    if not cost_center:
        raise HTTPException(status_code=404, detail="Cost center not found")
        
    # Check for dependencies
    # 1. Active Employees
    active_employees = db.query(Employee).filter(
        Employee.cost_center_id == cost_center.id,
        Employee.is_deleted == False
    ).count()
    
    if active_employees > 0:
        raise HTTPException(
            status_code=400,
            detail=f"Cannot delete cost center. There are {active_employees} active employees assigned to it."
        )
        
    # Perform soft delete
    try:
        cost_center.is_deleted = True
        cost_center.deleted_at = datetime.utcnow()
        db.add(cost_center)
        db.commit()
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e))
        
    return CostCenterDeleteResponse(
        success=True,
        message="Cost center deleted successfully",
        data=None
    )
