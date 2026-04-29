from typing import List, Optional, Union
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from app.api import deps
from app.models.employee import Location
from app.schemas.location import (
    LocationSchema,
    LocationCreate,
    LocationUpdate,
    LocationResponse,
    LocationListResponse,
    LocationDetailResponse,
    LocationDetailSchema,
    LocationDeleteResponse
)
from app.models.organization import Organization
from app.models.employee import Location, Employee
from app.schemas.employee import EmployeeListResponse
from datetime import datetime
import uuid

router = APIRouter()

@router.get("/", response_model=LocationListResponse)
def list_locations(
    db: Session = Depends(deps.get_db),
    current_org: Organization = Depends(deps.get_current_org),
    current_user: Union[Organization, Employee] = Depends(deps.get_current_user),
    is_active: Optional[bool] = Query(None, description="Filter by active status"),
    country: Optional[str] = Query(None, description="Filter by country"),
    search: Optional[str] = Query(None, description="Search by location_name"),
    page: Optional[int] = Query(None, ge=1, description="Page number"),
    limit: int = Query(10, ge=1, description="Items per page"),
    sort_by: Optional[str] = Query("Recent", description="Sort by field: location_code, location_name, is_active, Recent"),
    sort_order: str = Query("desc", description="Sort order: asc, desc"),
    authorized: bool = Depends(deps.check_permission("11"))
):
    """
    List all locations for the authenticated organization.
    """
    query = db.query(Location).filter(
        Location.organization_id == current_org.id,
        Location.is_deleted == False
    )
    
    if is_active is not None:
        query = query.filter(Location.is_active == is_active)
        
    if country:
        query = query.filter(Location.country == country)
        
    if search:
        search_term = f"%{search}%"
        query = query.filter(Location.location_name.ilike(search_term))
        
    # Sorting logic
    sort_mapping = {
        "location_code": Location.location_code,
        "location_name": Location.location_name,
        "is_active": Location.is_active,
        "Recent": Location.id
    }
    
    sort_field = sort_mapping.get(sort_by, Location.id)
    if sort_order.lower() == "asc":
        query = query.order_by(sort_field.asc())
    else:
        query = query.order_by(sort_field.desc())
        
    total_records = query.count()
    
    pagination_data = None
    if page is not None:
        total_pages = (total_records + limit - 1) // limit
        skip = (page - 1) * limit
        locations = query.offset(skip).limit(limit).all()
        pagination_data = {
            "total_records": total_records,
            "current_page": page,
            "total_pages": total_pages,
            "page_size": limit
        }
    else:
        locations = query.all()
        pagination_data = {
            "total_records": total_records,
            "current_page": 1,
            "total_pages": 1,
            "page_size": total_records if total_records > 0 else 0
        }
        
    if not locations:
        return LocationListResponse(
            success=False,
            message="No locations found"
        )
        
    return LocationListResponse(
        success=True,
        message="Locations retrieved successfully",
        data=locations,
        pagination=pagination_data
    )

@router.get("/lookup")
def lookup_locations(
    db: Session = Depends(deps.get_db),
    current_org: Organization = Depends(deps.get_current_org),
    search: Optional[str] = Query(None, description="Search by location_name or code"),
    limit: int = Query(100, ge=1, description="Limit lookup results")
):
    """
    Lite lookup endpoint for locations (ID, UUID, Name).
    Accessible to all authenticated users for filters/dropdowns.
    """
    query = db.query(Location).filter(
        Location.organization_id == current_org.id,
        Location.is_active == True,
        Location.is_deleted == False
    )
    
    if search:
        search_term = f"%{search}%"
        query = query.filter(
            (Location.location_name.ilike(search_term)) |
            (Location.location_code.ilike(search_term))
        )
        
    locations = query.order_by(Location.location_name.asc()).limit(limit).all()
    
    return {
        "success": True,
        "data": [{"uuid": l.uuid, "location_name": l.location_name} for l in locations]
    }

@router.post("/", response_model=LocationResponse)
def create_location(
    location_in: LocationCreate,
    db: Session = Depends(deps.get_db),
    current_org: Organization = Depends(deps.get_current_org),
    authorized: bool = Depends(deps.check_permission("9"))
):
    """
    Create a new location.
    """
    # Check if location with same code exists
    existing_loc = db.query(Location).filter(
        Location.organization_id == current_org.id,
        Location.location_code == location_in.location_code
    ).first()
    
    if existing_loc:
        raise HTTPException(
            status_code=400,
            detail=f"Location with code '{location_in.location_code}' already exists."
        )
        
    db_obj = Location(
        **location_in.model_dump(),
        organization_id=current_org.id
    )
    db.add(db_obj)
    try:
        db.commit()
        db.refresh(db_obj)
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e))
        
    return LocationResponse(
        success=True,
        message="Location created successfully",
        data=db_obj
    )

@router.get("/{location_uuid}", response_model=LocationDetailResponse)
def get_location(
    location_uuid: uuid.UUID,
    db: Session = Depends(deps.get_db),
    current_org: Organization = Depends(deps.get_current_org),
    authorized: bool = Depends(deps.check_permission("11"))
):
    """
    Get location details with employee count.
    """
    location = db.query(Location).filter(
        Location.uuid == location_uuid,
        Location.organization_id == current_org.id,
        Location.is_deleted == False
    ).first()
    
    if not location:
        raise HTTPException(status_code=404, detail="Location not found")
        
    # Count employees in this location
    employee_count = db.query(Employee).filter(
        Employee.location_id == location.id,
        Employee.is_deleted == False
    ).count()
    
    loc_data = LocationDetailSchema.model_validate(location)
    loc_data.employee_count = employee_count
    
    return LocationDetailResponse(
        success=True,
        message="Location retrieved successfully",
        data=loc_data
    )

@router.get("/{location_uuid}/employees", response_model=EmployeeListResponse)
def get_location_employees(
    location_uuid: uuid.UUID,
    page: Optional[int] = Query(None, ge=1, description="Page number"),
    limit: int = Query(10, ge=1, description="Items per page"),
    db: Session = Depends(deps.get_db),
    current_org: Organization = Depends(deps.get_current_org),
    authorized: bool = Depends(deps.check_permission("11"))
):
    """
    Get all employees in a location.
    """
    location = db.query(Location).filter(
        Location.uuid == location_uuid,
        Location.organization_id == current_org.id,
        Location.is_deleted == False
    ).first()
    
    if not location:
        raise HTTPException(status_code=404, detail="Location not found")
        
    query = db.query(Employee).filter(
        Employee.location_id == location.id,
        Employee.organization_id == current_org.id,
        Employee.is_deleted == False
    )
    
    total_records = query.count()
    
    pagination_data = None
    if page is not None:
        total_pages = (total_records + limit - 1) // limit
        skip = (page - 1) * limit
        employees = query.offset(skip).limit(limit).all()
        pagination_data = {
            "total_records": total_records,
            "current_page": page,
            "total_pages": total_pages,
            "page_size": limit
        }
    else:
        employees = query.all()
        pagination_data = {
            "total_records": total_records,
            "current_page": 1,
            "total_pages": 1,
            "page_size": total_records if total_records > 0 else 0
        }
        
    if not employees:
         return EmployeeListResponse(
            success=False,
            message="No employees found"
        )
        
    return EmployeeListResponse(
        success=True,
        message="Employees retrieved successfully",
        data=employees,
        pagination=pagination_data
    )

@router.put("/{location_uuid}", response_model=LocationResponse)
def update_location(
    location_uuid: uuid.UUID,
    location_in: LocationUpdate,
    db: Session = Depends(deps.get_db),
    current_org: Organization = Depends(deps.get_current_org),
    authorized: bool = Depends(deps.check_permission("10"))
):
    """
    Update a location.
    """
    location = db.query(Location).filter(
        Location.uuid == location_uuid,
        Location.organization_id == current_org.id,
        Location.is_deleted == False
    ).first()
    
    if not location:
        raise HTTPException(status_code=404, detail="Location not found")
        
    # Check duplicate code if being updated
    if location_in.location_code and location_in.location_code != location.location_code:
        existing_loc = db.query(Location).filter(
            Location.organization_id == current_org.id,
            Location.location_code == location_in.location_code,
            Location.is_deleted == False
        ).first()
        if existing_loc:
            raise HTTPException(
                status_code=400,
                detail=f"Location with code '{location_in.location_code}' already exists."
            )
            
    update_data = location_in.model_dump(exclude_unset=True)
    
    for field, value in update_data.items():
        setattr(location, field, value)
        
    db.add(location)
    try:
        db.commit()
        db.refresh(location)
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e))
        
    return LocationResponse(
        success=True,
        message="Location updated successfully",
        data=location
    )

@router.delete("/{location_uuid}", response_model=LocationDeleteResponse)
def delete_location(
    location_uuid: uuid.UUID,
    db: Session = Depends(deps.get_db),
    current_org: Organization = Depends(deps.get_current_org),
    authorized: bool = Depends(deps.check_permission("12"))
):
    """
    Delete a location (soft delete).
    """
    location = db.query(Location).filter(
        Location.uuid == location_uuid,
        Location.organization_id == current_org.id,
        Location.is_deleted == False
    ).first()
    
    if not location:
        raise HTTPException(status_code=404, detail="Location not found")
        
    # Check for dependencies
    # 1. Active Employees
    active_employees = db.query(Employee).filter(
        Employee.location_id == location.id,
        Employee.is_deleted == False
    ).count()
    
    if active_employees > 0:
        raise HTTPException(
            status_code=400,
            detail=f"Cannot delete location. There are {active_employees} active employees assigned to it."
        )
        
    # Perform soft delete
    try:
        location.is_deleted = True
        location.deleted_at = datetime.utcnow()
        db.add(location)
        db.commit()
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e))
        
    return LocationDeleteResponse(
        success=True,
        message="Location deleted successfully",
        data=None
    )
