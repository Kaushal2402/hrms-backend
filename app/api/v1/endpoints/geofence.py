from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.api import deps
from app.models.attendance import GeofenceLocation
from app.models.employee import Location
from app.models.organization import Organization
from app.schemas.attendance import GeofenceValidationRequest, GeofenceValidationResponse, GeofenceValidationResult
from app.utils.geo import haversine_distance
from app.core.permissions import GeofencePermissions

router = APIRouter()

@router.post("/validate-location", response_model=GeofenceValidationResponse)
def validate_geofence_location(
    request: GeofenceValidationRequest,
    db: Session = Depends(deps.get_db),
    current_org: Organization = Depends(deps.get_current_org),
    _: bool = Depends(deps.check_permission(GeofencePermissions.READ))
):
    """
    Validate if the provided coordinates are within any active geofence for the organization.
    If location_uuid is provided, it only checks geofences for that specific location.
    """
    query = db.query(GeofenceLocation).filter(
        GeofenceLocation.organization_id == current_org.id,
        GeofenceLocation.is_active == True,
        GeofenceLocation.is_deleted == False
    )

    if request.location_uuid:
        location = db.query(Location.id).filter(
            Location.uuid == request.location_uuid,
            Location.organization_id == current_org.id
        ).first()
        if location:
            query = query.filter(GeofenceLocation.location_id == location[0])
        else:
            # If location provided but not found, check nothing
            query = query.filter(GeofenceLocation.id == -1)

    geofences = query.all()

    if not geofences:
        return GeofenceValidationResponse(
            success=True,
            message="No active geofences found for validation.",
            data=GeofenceValidationResult(
                is_within_geofence=True, # Default to True if no fences defined? Or False? 
                # Usually if no geofence is defined, we might allow it or handle it in policy.
                # For this validation endpoint, we'll say False but with a message.
                distance_meters=0.0
            )
        )

    min_distance = float('inf')
    matched_geofence = None

    for gf in geofences:
        distance = haversine_distance(
            request.latitude, request.longitude, 
            gf.latitude, gf.longitude
        )
        
        if distance <= gf.radius_meters:
            return GeofenceValidationResponse(
                success=True,
                message="Coordinates are within geofence.",
                data=GeofenceValidationResult(
                    is_within_geofence=True,
                    distance_meters=round(distance, 2),
                    geofence_name=gf.location_name,
                    geofence_uuid=gf.uuid
                )
            )
        
        if distance < min_distance:
            min_distance = distance
            matched_geofence = gf

    return GeofenceValidationResponse(
        success=True,
        message="Coordinates are outside all applicable geofences.",
        data=GeofenceValidationResult(
            is_within_geofence=False,
            distance_meters=round(min_distance, 2),
            geofence_name=matched_geofence.location_name if matched_geofence else None,
            geofence_uuid=matched_geofence.uuid if matched_geofence else None
        )
    )
