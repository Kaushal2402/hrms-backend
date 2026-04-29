from typing import List, Optional
import uuid
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from fastapi.responses import JSONResponse
from datetime import datetime

from app.api import deps
from app.models.attendance import LeaveType
from app.models.organization import Organization
from app.schemas.leave import LeaveTypeListResponse, LeaveTypeCreate, LeaveTypeResponse, LeaveTypeUpdate, LeaveTypeLookupResponse

router = APIRouter()

@router.get("/", response_model=LeaveTypeListResponse)
def list_leave_types(
    db: Session = Depends(deps.get_db),
    current_org: Organization = Depends(deps.get_current_org),
    page: Optional[int] = Query(None, ge=1, description="Page number"),
    limit: int = Query(10, ge=1, description="Items per page"),
    is_active: Optional[bool] = Query(None, description="Filter by active status"),
    search: Optional[str] = Query(None, description="Search by leave name or code"),
    sort_by: str = Query("leave_name", description="Sort by leave_code, leave_name, is_paid, unit_type, is_active"),
    order: str = Query("asc", description="Sort order (asc, desc)"),
    authorized: bool = Depends(deps.check_permission("47"))
):
    """
    List all leave types for the organization with pagination and filtering.
    """
    query = db.query(LeaveType).filter(
        LeaveType.organization_id == current_org.id,
        LeaveType.is_deleted == False
    )
    
    # Optional filtering
    if is_active is not None:
        query = query.filter(LeaveType.is_active == is_active)
        
    if search:
        search_term = f"%{search}%"
        query = query.filter(
            (LeaveType.leave_name.ilike(search_term)) |
            (LeaveType.leave_code.ilike(search_term))
        )
        
    # Sorting
    sort_map = {
        "leave_code": LeaveType.leave_code,
        "leave_name": LeaveType.leave_name,
        "is_paid": LeaveType.is_paid,
        "unit_type": LeaveType.unit_type,
        "is_active": LeaveType.is_active
    }
    
    sort_column = sort_map.get(sort_by, LeaveType.leave_name)
    if order.lower() == "desc":
        query = query.order_by(sort_column.desc())
    else:
        query = query.order_by(sort_column.asc())
    
    # query = query.order_by(LeaveType.display_order.asc(), LeaveType.leave_name.asc())
    
    # Pagination
    total_records = query.count()
    
    pagination_data = None
    if page is not None:
        total_pages = (total_records + limit - 1) // limit
        skip = (page - 1) * limit
        leave_types = query.offset(skip).limit(limit).all()
        pagination_data = {
            "total_records": total_records,
            "current_page": page,
            "total_pages": total_pages,
            "page_size": limit
        }
    else:
        leave_types = query.all()
        pagination_data = {
            "total_records": total_records,
            "current_page": 1,
            "total_pages": 1,
            "page_size": total_records if total_records > 0 else 0
        }
        
    return LeaveTypeListResponse(
        success=True,
        message="Leave types retrieved successfully",
        data=leave_types,
        pagination=pagination_data
    )

@router.get("/lookup", response_model=LeaveTypeLookupResponse)
def lookup_leave_types(
    db: Session = Depends(deps.get_db),
    current_org: Organization = Depends(deps.get_current_org),
    search: Optional[str] = Query(None, description="Search by leave name or code"),
    limit: int = Query(100, ge=1, description="Limit lookup results")
):
    """
    Get a simplified list of active leave types for lookups.
    Only requires authentication.
    """
    query = db.query(LeaveType).filter(
        LeaveType.organization_id == current_org.id,
        LeaveType.is_active == True,
        LeaveType.is_deleted == False
    )
    
    if search:
        search_term = f"%{search}%"
        query = query.filter(
            (LeaveType.leave_name.ilike(search_term)) |
            (LeaveType.leave_code.ilike(search_term))
        )
        
    leave_types = query.order_by(LeaveType.leave_name.asc()).limit(limit).all()
    
    return LeaveTypeLookupResponse(
        success=True,
        message="Leave types retrieved successfully",
        data=leave_types
    )

@router.post("/", response_model=LeaveTypeResponse)
def create_leave_type(
    leave_type_in: LeaveTypeCreate,
    db: Session = Depends(deps.get_db),
    current_org: Organization = Depends(deps.get_current_org),
    authorized: bool = Depends(deps.check_permission("48"))
):
    """
    Create a new leave type.
    """
    # 1. Check for duplicates (code or name)
    existing = db.query(LeaveType).filter(
        LeaveType.organization_id == current_org.id,
        (LeaveType.leave_code == leave_type_in.leave_code) | (LeaveType.leave_name == leave_type_in.leave_name)
    ).first()
    
    if existing:
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={"success": False, "message": "Leave type with this code or name already exists", "data": None}
        )
        
    # 2. Create Object
    # We map fields directly. Since schema fields match model fields largely, we can unpack.
    # But filtering fields is safer.
    
    leave_type_data = leave_type_in.dict()
    leave_type = LeaveType(**leave_type_data)
    leave_type.organization_id = current_org.id
    leave_type.organization_id = current_org.id
    # leave_type.created_by = current_user.id # Skipping for now
    
    db.add(leave_type)
    db.commit()
    db.refresh(leave_type)
    
    return LeaveTypeResponse(
        success=True,
        message="Leave type created successfully",
        data=leave_type
    )

@router.get("/{leave_type_uuid}", response_model=LeaveTypeResponse)
def get_leave_type(
    leave_type_uuid: uuid.UUID,
    db: Session = Depends(deps.get_db),
    current_org: Organization = Depends(deps.get_current_org),
    authorized: bool = Depends(deps.check_permission("47"))
):
    """
    Get detailed information for a specific leave type.
    """
    leave_type = db.query(LeaveType).filter(
        LeaveType.uuid == leave_type_uuid,
        LeaveType.organization_id == current_org.id,
        LeaveType.is_deleted == False
    ).first()
    
    if not leave_type:
        return JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND,
            content={"success": False, "message": "Leave type not found", "data": None}
        )
        
    return LeaveTypeResponse(
        success=True,
        message="Leave type retrieved successfully",
        data=leave_type
    )

@router.put("/{leave_type_uuid}", response_model=LeaveTypeResponse)
def update_leave_type(
    leave_type_uuid: uuid.UUID,
    leave_type_in: LeaveTypeUpdate,
    db: Session = Depends(deps.get_db),
    current_org: Organization = Depends(deps.get_current_org),
    authorized: bool = Depends(deps.check_permission("49"))
):
    """
    Update an existing leave type.
    """
    leave_type = db.query(LeaveType).filter(
        LeaveType.uuid == leave_type_uuid,
        LeaveType.organization_id == current_org.id,
        LeaveType.is_deleted == False
    ).first()
    
    if not leave_type:
        return JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND,
            content={"success": False, "message": "Leave type not found", "data": None}
        )
        
    # Check for duplicates if name or code is being updated
    if leave_type_in.leave_code or leave_type_in.leave_name:
        existing = db.query(LeaveType).filter(
            LeaveType.organization_id == current_org.id,
            (LeaveType.id != leave_type.id),
            (
                (LeaveType.leave_code == leave_type_in.leave_code) | 
                (LeaveType.leave_name == leave_type_in.leave_name)
            )
        ).first()
        
        if existing:
            # Check which one conflicts or if both
            msg = "Leave type with this code or name already exists"
            if leave_type_in.leave_code and existing.leave_code == leave_type_in.leave_code:
                 msg = "Leave type with this code already exists"
            elif leave_type_in.leave_name and existing.leave_name == leave_type_in.leave_name:
                 msg = "Leave type with this name already exists"
                
            return JSONResponse(
                status_code=status.HTTP_400_BAD_REQUEST,
                content={"success": False, "message": msg, "data": None}
            )

    update_data = leave_type_in.dict(exclude_unset=True)
    for field, value in update_data.items():
        setattr(leave_type, field, value)
        
    db.commit()
    db.refresh(leave_type)
    
    return LeaveTypeResponse(
        success=True,
        message="Leave type updated successfully",
        data=leave_type
    )

@router.delete("/{leave_type_uuid}")
def delete_leave_type(
    leave_type_uuid: uuid.UUID,
    db: Session = Depends(deps.get_db),
    current_org: Organization = Depends(deps.get_current_org),
    authorized: bool = Depends(deps.check_permission("50"))
):
    """
    Soft delete a leave type.
    """
    leave_type = db.query(LeaveType).filter(
        LeaveType.uuid == leave_type_uuid,
        LeaveType.organization_id == current_org.id,
        LeaveType.is_deleted == False
    ).first()
    
    if not leave_type:
        return JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND,
            content={"success": False, "message": "Leave type not found", "data": None}
        )
        
    leave_type.is_deleted = True
    leave_type.deleted_at = datetime.utcnow()
    leave_type.is_active = False # Deactivate as well
    
    db.commit()
    
    return {
        "success": True, 
        "message": "Leave type deleted successfully"
    }
