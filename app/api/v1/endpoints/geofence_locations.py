import uuid
from typing import List, Optional
from datetime import datetime
from fastapi import APIRouter, Depends, Query, HTTPException, status
from sqlalchemy.orm import Session
from app.api import deps
from app.models.attendance import GeofenceLocation
from app.models.employee import Location
from app.models.organization import Organization
from app.schemas.attendance import (
    GeofenceLocationListResponse, 
    GeofenceLocationCreate, 
    GeofenceLocationResponse,
    GeofenceLocationUpdate,
    GeofenceLocationSchema
)
from app.core.permissions import GeofencePermissions

router = APIRouter()

def map_geofence_response(geofence: GeofenceLocation, location_uuid: Optional[uuid.UUID] = None) -> GeofenceLocationSchema:
    """Helper to map ORM and resolved UUID to schema."""
    result = GeofenceLocationSchema.model_validate(geofence)
    result.location_uuid = location_uuid
    return result

@router.post("/", response_model=GeofenceLocationResponse)
def create_geofence_location(
    geofence_in: GeofenceLocationCreate,
    db: Session = Depends(deps.get_db),
    current_org: Organization = Depends(deps.get_current_org),
    _: bool = Depends(deps.check_permission(GeofencePermissions.CREATE))
):
    """
    Create a new geofence location for the organization.
    """
    # 1. Resolve UUID to ID
    geofence_data = geofence_in.model_dump(exclude={'location_uuid'})
    if geofence_in.location_uuid:
        location = db.query(Location).filter(
            Location.uuid == geofence_in.location_uuid,
            Location.organization_id == current_org.id,
            Location.is_deleted == False
        ).first()
        if location:
            geofence_data['location_id'] = location.id

    # 2. Create record
    geofence = GeofenceLocation(
        **geofence_data,
        organization_id=current_org.id
    )

    db.add(geofence)
    try:
        db.commit()
        db.refresh(geofence)
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create geofence location: {str(e)}"
        )

    return GeofenceLocationResponse(
        success=True,
        message="Geofence location created successfully",
        data=map_geofence_response(geofence, geofence_in.location_uuid)
    )

@router.get("/", response_model=GeofenceLocationListResponse)
def list_geofence_locations(
    db: Session = Depends(deps.get_db),
    current_org: Organization = Depends(deps.get_current_org),
    search: Optional[str] = Query(None, description="Search by location name"),
    location_uuid: Optional[uuid.UUID] = Query(None, alias="location_id", description="Filter by location UUID"),
    is_active: Optional[bool] = Query(None, description="Filter by active status"),
    sort_by: str = Query("location_name", description="Sort by field: location_name, radius_meters, is_active"),
    order: str = Query("asc", description="Sort order: asc, desc"),
    page: int = Query(1, ge=1, description="Page number"),
    limit: int = Query(10, ge=1, description="Items per page"),
    _: bool = Depends(deps.check_permission(GeofencePermissions.READ))
):
    """
    List geofence locations with filtering, search, sorting and pagination.
    """
    query = db.query(
        GeofenceLocation,
        Location.uuid.label("location_uuid")
    ).outerjoin(
        Location, GeofenceLocation.location_id == Location.id
    ).filter(
        GeofenceLocation.organization_id == current_org.id,
        GeofenceLocation.is_deleted == False
    )

    if search:
        query = query.filter(GeofenceLocation.location_name.ilike(f"%{search}%"))

    if location_uuid is not None:
        query = query.filter(Location.uuid == location_uuid)
    
    if is_active is not None:
        query = query.filter(GeofenceLocation.is_active == is_active)

    # Sorting logic
    sort_column = getattr(GeofenceLocation, sort_by, GeofenceLocation.location_name)
    if order.lower() == "desc":
        query = query.order_by(sort_column.desc())
    else:
        query = query.order_by(sort_column.asc())

    # Pagination
    total_records = query.count()
    total_pages = (total_records + limit - 1) // limit
    skip = (page - 1) * limit

    results = query.offset(skip).limit(limit).all()
    
    geofences_data = [map_geofence_response(row[0], row[1]) for row in results]

    pagination = {
        "total_records": total_records,
        "current_page": page,
        "total_pages": total_pages,
        "page_size": limit
    }

    return GeofenceLocationListResponse(
        success=True,
        message="Geofence locations retrieved successfully",
        data=geofences_data,
        pagination=pagination
    )

@router.get("/{geofence_id}", response_model=GeofenceLocationResponse)
def get_geofence_location(
    geofence_id: str,
    db: Session = Depends(deps.get_db),
    current_org: Organization = Depends(deps.get_current_org),
    _: bool = Depends(deps.check_permission(GeofencePermissions.READ))
):
    """
    Get detailed information about a specific geofence location.
    Supports both internal ID and UUID.
    """
    geofence = None
    try:
        # Try resolving by UUID first
        uuid_obj = uuid.UUID(geofence_id)
        geofence_row = db.query(
            GeofenceLocation,
            Location.uuid.label("location_uuid")
        ).outerjoin(
            Location, GeofenceLocation.location_id == Location.id
        ).filter(
            GeofenceLocation.uuid == uuid_obj,
            GeofenceLocation.organization_id == current_org.id,
            GeofenceLocation.is_deleted == False
        ).first()
        geofence = geofence_row[0] if geofence_row else None
        loc_uuid = geofence_row[1] if geofence_row else None
    except ValueError:
        # Fallback to internal ID
        try:
            geofence_row = db.query(
                GeofenceLocation,
                Location.uuid.label("location_uuid")
            ).outerjoin(
                Location, GeofenceLocation.location_id == Location.id
            ).filter(
                GeofenceLocation.id == int(geofence_id),
                GeofenceLocation.organization_id == current_org.id,
                GeofenceLocation.is_deleted == False
            ).first()
            geofence = geofence_row[0] if geofence_row else None
            loc_uuid = geofence_row[1] if geofence_row else None
        except ValueError:
            pass

    if not geofence:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Geofence location not found"
        )

    return GeofenceLocationResponse(
        success=True,
        message="Geofence location details retrieved successfully",
        data=map_geofence_response(geofence, loc_uuid)
    )

@router.put("/{geofence_id}", response_model=GeofenceLocationResponse)
def update_geofence_location(
    geofence_id: str,
    geofence_in: GeofenceLocationUpdate,
    db: Session = Depends(deps.get_db),
    current_org: Organization = Depends(deps.get_current_org),
    _: bool = Depends(deps.check_permission(GeofencePermissions.UPDATE))
):
    """
    Update an existing geofence location.
    """
    # 1. Fetch geofence
    geofence = None
    try:
        uuid_obj = uuid.UUID(geofence_id)
        geofence = db.query(GeofenceLocation).filter(
            GeofenceLocation.uuid == uuid_obj,
            GeofenceLocation.organization_id == current_org.id,
            GeofenceLocation.is_deleted == False
        ).first()
    except ValueError:
        try:
            geofence = db.query(GeofenceLocation).filter(
                GeofenceLocation.id == int(geofence_id),
                GeofenceLocation.organization_id == current_org.id,
                GeofenceLocation.is_deleted == False
            ).first()
        except ValueError:
            pass

    if not geofence:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Geofence location not found"
        )

    # 2. Apply updates
    update_data = geofence_in.model_dump(exclude_unset=True, exclude={'location_uuid'})
    
    if geofence_in.location_uuid is not None:
        location = db.query(Location).filter(
            Location.uuid == geofence_in.location_uuid,
            Location.organization_id == current_org.id,
            Location.is_deleted == False
        ).first()
        if location:
            update_data['location_id'] = location.id
        else:
            update_data['location_id'] = None

    for field, value in update_data.items():
        setattr(geofence, field, value)

    try:
        db.commit()
        db.refresh(geofence)
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update geofence location: {str(e)}"
        )

    return GeofenceLocationResponse(
        success=True,
        message="Geofence location updated successfully",
        data=map_geofence_response(geofence, geofence_in.location_uuid)
    )

@router.delete("/{geofence_id}", response_model=dict)
def delete_geofence_location(
    geofence_id: str,
    db: Session = Depends(deps.get_db),
    current_org: Organization = Depends(deps.get_current_org),
    _: bool = Depends(deps.check_permission(GeofencePermissions.DELETE))
):
    """
    Soft delete a geofence location.
    """
    geofence = None
    try:
        uuid_obj = uuid.UUID(geofence_id)
        geofence = db.query(GeofenceLocation).filter(
            GeofenceLocation.uuid == uuid_obj,
            GeofenceLocation.organization_id == current_org.id,
            GeofenceLocation.is_deleted == False
        ).first()
    except ValueError:
        try:
            geofence = db.query(GeofenceLocation).filter(
                GeofenceLocation.id == int(geofence_id),
                GeofenceLocation.organization_id == current_org.id,
                GeofenceLocation.is_deleted == False
            ).first()
        except ValueError:
            pass

    if not geofence:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Geofence location not found"
        )

    # Soft delete
    geofence.is_deleted = True
    geofence.deleted_at = datetime.utcnow()
    geofence.is_active = False

    try:
        db.commit()
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete geofence location: {str(e)}"
        )

    return {
        "success": True,
        "message": "Geofence location deleted successfully",
        "data": None
    }
