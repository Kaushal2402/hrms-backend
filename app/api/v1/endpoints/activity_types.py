from typing import Optional, Union, List
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
import uuid
from datetime import datetime

from app.api import deps
from app.models.organization import Organization
from app.models.employee import Employee
from app.models.projects import ActivityType
from app.schemas.projects import (
    ActivityTypeCreate, ActivityTypeUpdate, ActivityTypeSchema,
    ActivityTypeResponse, ActivityTypeListResponse
)

router = APIRouter()


def _require(db, user, code, action):
    if isinstance(user, Organization):
        return
    if not deps.has_permission(db, user, code):
        raise HTTPException(status_code=403, detail=f"No permission to {action} activity types (code: {code})")


def _org_id(user):
    return user.id if isinstance(user, Organization) else user.organization_id


# -------------------------------------------------------
# LOOKUP — open (auth only)
# -------------------------------------------------------
@router.get("/lookup")
def lookup_activity_types(
    db: Session = Depends(deps.get_db),
    current_user: Union[Organization, Employee] = Depends(deps.get_current_user),
):
    """Open lookup for timesheet entry dropdowns. No RBAC required."""
    types = db.query(ActivityType).filter(
        ActivityType.organization_id == _org_id(current_user),
        ActivityType.is_active == True,
        ActivityType.is_deleted == False
    ).order_by(ActivityType.activity_name).all()
    return {
        "success": True,
        "data": [{"uuid": t.uuid, "activity_name": t.activity_name, "activity_code": t.activity_code, "is_billable_default": t.is_billable_default, "color_code": t.color_code} for t in types]
    }


# -------------------------------------------------------
# LIST — Permission 92
# -------------------------------------------------------
@router.get("/", response_model=ActivityTypeListResponse)
def list_activity_types(
    db: Session = Depends(deps.get_db),
    current_user: Union[Organization, Employee] = Depends(deps.get_current_user),
    is_active: Optional[bool] = Query(None),
):
    _require(db, current_user, "92", "list")
    types = db.query(ActivityType).filter(
        ActivityType.organization_id == _org_id(current_user),
        ActivityType.is_deleted == False
    )
    if is_active is not None:
        types = types.filter(ActivityType.is_active == is_active)
    types = types.order_by(ActivityType.activity_name).all()
    return ActivityTypeListResponse(success=True, message="Activity types retrieved", data=[ActivityTypeSchema.model_validate(t) for t in types])


# -------------------------------------------------------
# GET SINGLE — Permission 92
# -------------------------------------------------------
@router.get("/{activity_uuid}", response_model=ActivityTypeResponse)
def get_activity_type(
    activity_uuid: uuid.UUID,
    db: Session = Depends(deps.get_db),
    current_user: Union[Organization, Employee] = Depends(deps.get_current_user)
):
    _require(db, current_user, "92", "view")
    activity = db.query(ActivityType).filter(
        ActivityType.uuid == activity_uuid,
        ActivityType.organization_id == _org_id(current_user),
        ActivityType.is_deleted == False
    ).first()
    if not activity:
        raise HTTPException(status_code=404, detail="Activity type not found")
    return ActivityTypeResponse(success=True, message="Activity type retrieved", data=ActivityTypeSchema.model_validate(activity))


# -------------------------------------------------------
# CREATE — Permission 92
# -------------------------------------------------------
@router.post("/", response_model=ActivityTypeResponse, status_code=status.HTTP_201_CREATED)
def create_activity_type(
    type_in: ActivityTypeCreate,
    db: Session = Depends(deps.get_db),
    current_user: Union[Organization, Employee] = Depends(deps.get_current_user)
):
    _require(db, current_user, "92", "create")
    org_id = _org_id(current_user)

    if db.query(ActivityType).filter(
        ActivityType.organization_id == org_id,
        ActivityType.activity_code == type_in.activity_code,
        ActivityType.is_deleted == False
    ).first():
        raise HTTPException(status_code=400, detail=f"Activity code '{type_in.activity_code}' already exists")

    employee_id = current_user.id if isinstance(current_user, Employee) else None
    activity = ActivityType(organization_id=org_id, created_by=employee_id, **type_in.model_dump())
    db.add(activity)
    db.commit()
    db.refresh(activity)
    return ActivityTypeResponse(success=True, message="Activity type created", data=ActivityTypeSchema.model_validate(activity))


# -------------------------------------------------------
# UPDATE — Permission 92
# -------------------------------------------------------
@router.put("/{activity_uuid}", response_model=ActivityTypeResponse)
def update_activity_type(
    activity_uuid: uuid.UUID,
    type_in: ActivityTypeUpdate,
    db: Session = Depends(deps.get_db),
    current_user: Union[Organization, Employee] = Depends(deps.get_current_user)
):
    _require(db, current_user, "92", "update")
    activity = db.query(ActivityType).filter(
        ActivityType.uuid == activity_uuid,
        ActivityType.organization_id == _org_id(current_user),
        ActivityType.is_deleted == False
    ).first()
    if not activity:
        raise HTTPException(status_code=404, detail="Activity type not found")
    for field, value in type_in.model_dump(exclude_unset=True).items():
        setattr(activity, field, value)
    db.commit()
    db.refresh(activity)
    return ActivityTypeResponse(success=True, message="Activity type updated", data=ActivityTypeSchema.model_validate(activity))


# -------------------------------------------------------
# DELETE — Permission 92
# -------------------------------------------------------
@router.delete("/{activity_uuid}")
def delete_activity_type(
    activity_uuid: uuid.UUID,
    db: Session = Depends(deps.get_db),
    current_user: Union[Organization, Employee] = Depends(deps.get_current_user)
):
    _require(db, current_user, "92", "delete")
    activity = db.query(ActivityType).filter(
        ActivityType.uuid == activity_uuid,
        ActivityType.organization_id == _org_id(current_user),
        ActivityType.is_deleted == False
    ).first()
    if not activity:
        raise HTTPException(status_code=404, detail="Activity type not found")
    activity.is_deleted = True
    activity.is_active = False
    db.commit()
    return {"success": True, "message": "Activity type deleted"}
