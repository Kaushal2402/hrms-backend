import uuid
from typing import List, Optional, Union
from fastapi import APIRouter, Depends, Query, HTTPException, status
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
from sqlalchemy import or_
from datetime import datetime

from app.api import deps
from app.models.attendance import ShiftMaster
from app.models.employee import Employee
from app.models.organization import Organization
from app.schemas.attendance import (
    ShiftSchema, ShiftListResponse, ShiftType, 
    ShiftCreate, ShiftResponse, ShiftUpdate
)
from app.schemas.department import PaginationData

router = APIRouter()


@router.get("/", response_model=ShiftListResponse)
def list_shifts(
    db: Session = Depends(deps.get_db),
    current_user: Union[Organization, Employee] = Depends(deps.get_current_user),
    page: Optional[int] = Query(None, ge=1, description="Page number"),
    limit: int = Query(10, ge=1, description="Items per page"),
    sort_by: Optional[str] = Query(None, description="Sort by field"),
    sort_order: Optional[str] = Query("desc", description="Sort order (asc/desc)"),
    shift_type: Optional[ShiftType] = Query(None, description="Filter by Shift Type"),
    is_active: Optional[bool] = Query(None, description="Filter by Active Status"),
    search: Optional[str] = Query(None, description="Search term (Name or Code)"),
    authorized: bool = Depends(deps.check_permission("21"))
):
    """
    List all shifts with filtering and pagination.
    """
    current_org_id = current_user.id if isinstance(current_user, Organization) else current_user.organization_id
    query = db.query(ShiftMaster).filter(
        ShiftMaster.organization_id == current_org_id,
        ShiftMaster.is_deleted == False
    )
    
    # 1. Filters
    if shift_type:
        query = query.filter(ShiftMaster.shift_type == shift_type)
    
    if is_active is not None:
        query = query.filter(ShiftMaster.is_active == is_active)
        
    if search:
        search_term = f"%{search}%"
        query = query.filter(
            or_(
                ShiftMaster.shift_name.ilike(search_term),
                ShiftMaster.shift_code.ilike(search_term)
            )
        )
    
    # 2. Sorting
    sort_field = ShiftMaster.created_at # Default
    if sort_by:
        if sort_by == "shift_name":
            sort_field = ShiftMaster.shift_name
        elif sort_by == "shift_code":
            sort_field = ShiftMaster.shift_code
        elif sort_by == "start_time":
            sort_field = ShiftMaster.start_time
        elif sort_by == "end_time":
            sort_field = ShiftMaster.end_time
        elif sort_by == "is_active":
            sort_field = ShiftMaster.is_active
            
    if sort_order == "asc":
        query = query.order_by(sort_field.asc())
    else:
        query = query.order_by(sort_field.desc())
    
    # 3. Pagination
    total_records = query.count()
    
    pagination_data = None
    if page is not None:
        total_pages = (total_records + limit - 1) // limit
        skip = (page - 1) * limit
        shifts = query.offset(skip).limit(limit).all()
        pagination_data = {
            "total_records": total_records,
            "current_page": page,
            "total_pages": total_pages,
            "page_size": limit
        }
    else:
        shifts = query.all()
        pagination_data = {
            "total_records": total_records,
            "current_page": 1,
            "total_pages": 1,
            "page_size": total_records if total_records > 0 else 0
        }
    
    if not shifts:
        return ShiftListResponse(
            success=False,
            message="No shifts found"
        )
    
    return ShiftListResponse(
        success=True,
        message="Shifts retrieved successfully",
        data=shifts,
        pagination=pagination_data
    )

@router.get("/lookup")
def lookup_shifts(
    db: Session = Depends(deps.get_db),
    current_org: Organization = Depends(deps.get_current_org),
    search: Optional[str] = Query(None, description="Search term (Name or Code)"),
    limit: int = Query(100, ge=1, description="Limit lookup results")
):
    """
    Lite lookup endpoint for shifts (UUID, Name, Code).
    Accessible to all authenticated users for filters/dropdowns.
    """
    query = db.query(ShiftMaster).filter(
        ShiftMaster.organization_id == current_org.id,
        ShiftMaster.is_active == True,
        ShiftMaster.is_deleted == False
    )
    
    if search:
        search_term = f"%{search}%"
        query = query.filter(
            or_(
                ShiftMaster.shift_name.ilike(search_term),
                ShiftMaster.shift_code.ilike(search_term)
            )
        )
        
    shifts = query.order_by(ShiftMaster.shift_name.asc()).limit(limit).all()
    
    return {
        "success": True,
        "data": [
            {
                "uuid": shift.uuid, 
                "shift_name": shift.shift_name,
                "shift_code": shift.shift_code
            } for shift in shifts
        ]
    }

@router.post("/", response_model=ShiftResponse)
def create_shift(
    *,
    db: Session = Depends(deps.get_db),
    current_user: Union[Organization, Employee] = Depends(deps.get_current_user),
    shift_in: ShiftCreate,
    authorized: bool = Depends(deps.check_permission("22"))
):
    """
    Create a new shift.
    """
    current_org_id = current_user.id if isinstance(current_user, Organization) else current_user.organization_id
    # Check if shift code already exists for this organization
    existing_shift = db.query(ShiftMaster).filter(
        ShiftMaster.organization_id == current_org_id,
        ShiftMaster.shift_code == shift_in.shift_code
    ).first()
    
    if existing_shift:
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={
                "success": False,
                "message": f"Shift code '{shift_in.shift_code}' already exists for this organization.",
                "data": None
            }
        )
    
    # If is_default is true, unset other defaults
    if shift_in.is_default:
        db.query(ShiftMaster).filter(
            ShiftMaster.organization_id == current_org_id,
            ShiftMaster.is_default == True
        ).update({ShiftMaster.is_default: False})

    # Create new shift object
    db_shift = ShiftMaster(
        **shift_in.model_dump(),
        organization_id=current_org_id
    )
    
    db.add(db_shift)
    db.commit()
    db.refresh(db_shift)
    
    return ShiftResponse(
        success=True,
        message="Shift created successfully",
        data=db_shift
    )

@router.get("/{shift_uuid}", response_model=ShiftResponse)
def get_shift(
    shift_uuid: uuid.UUID,
    db: Session = Depends(deps.get_db),
    current_user: Union[Organization, Employee] = Depends(deps.get_current_user),
    authorized: bool = Depends(deps.check_permission("21"))
):
    """
    Get shift details by UUID.
    """
    current_org_id = current_user.id if isinstance(current_user, Organization) else current_user.organization_id
    shift = db.query(ShiftMaster).filter(
        ShiftMaster.uuid == shift_uuid,
        ShiftMaster.organization_id == current_org_id,
        ShiftMaster.is_deleted == False
    ).first()
    
    if not shift:
        return JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND,
            content={
                "success": False,
                "message": "Shift not found",
                "data": None
            }
        )
        
    return ShiftResponse(
        success=True,
        message="Shift retrieved successfully",
        data=shift
    )

@router.put("/{shift_uuid}", response_model=ShiftResponse)
def update_shift(
    shift_uuid: uuid.UUID,
    shift_in: ShiftUpdate,
    db: Session = Depends(deps.get_db),
    current_user: Union[Organization, Employee] = Depends(deps.get_current_user),
    authorized: bool = Depends(deps.check_permission("23"))
):
    """
    Update a shift.
    """
    current_org_id = current_user.id if isinstance(current_user, Organization) else current_user.organization_id
    shift = db.query(ShiftMaster).filter(
        ShiftMaster.uuid == shift_uuid,
        ShiftMaster.organization_id == current_org_id,
        ShiftMaster.is_deleted == False
    ).first()
    
    if not shift:
        return JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND,
            content={
                "success": False,
                "message": "Shift not found",
                "data": None
            }
        )
    
    # Check if updated shift code already exists for ANOTHER shift in this organization
    if shift_in.shift_code and shift_in.shift_code != shift.shift_code:
        existing_shift = db.query(ShiftMaster).filter(
            ShiftMaster.organization_id == current_org_id,
            ShiftMaster.shift_code == shift_in.shift_code,
            ShiftMaster.uuid != shift_uuid
        ).first()
        
        if existing_shift:
            return JSONResponse(
                status_code=status.HTTP_400_BAD_REQUEST,
                content={
                    "success": False,
                    "message": f"Shift code '{shift_in.shift_code}' already exists for another shift in this organization.",
                    "data": None
                }
            )
    
    # Update fields
    update_data = shift_in.model_dump(exclude_unset=True)
    
    # If is_default is true, unset other defaults
    if update_data.get('is_default'):
        db.query(ShiftMaster).filter(
            ShiftMaster.organization_id == current_org_id,
            ShiftMaster.is_default == True
        ).update({ShiftMaster.is_default: False})
    for field, value in update_data.items():
        setattr(shift, field, value)
    
    db.add(shift)
    db.commit()
    db.refresh(shift)
    
    return ShiftResponse(
        success=True,
        message="Shift updated successfully",
        data=shift
    )

@router.delete("/{shift_uuid}", response_model=ShiftResponse)
def delete_shift(
    shift_uuid: uuid.UUID,
    db: Session = Depends(deps.get_db),
    current_user: Union[Organization, Employee] = Depends(deps.get_current_user),
    authorized: bool = Depends(deps.check_permission("24"))
):
    """
    Soft delete a shift.
    """
    current_org_id = current_user.id if isinstance(current_user, Organization) else current_user.organization_id
    shift = db.query(ShiftMaster).filter(
        ShiftMaster.uuid == shift_uuid,
        ShiftMaster.organization_id == current_org_id,
        ShiftMaster.is_deleted == False
    ).first()
    
    if not shift:
        return JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND,
            content={
                "success": False,
                "message": "Shift not found",
                "data": None
            }
        )
    
    # Check if shift is being used? 
    # (Optional: check for active shift assignments before deleting)
    
    # Perform soft delete
    shift.is_deleted = True
    shift.deleted_at = datetime.utcnow()
    shift.is_active = False # Also deactivate
    
    db.add(shift)
    db.commit()
    
    return ShiftResponse(
        success=True,
        message="Shift deleted successfully",
        data=None
    )
