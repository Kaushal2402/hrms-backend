from typing import Optional, Union
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from sqlalchemy import or_
import uuid

from app.api import deps
from app.models.organization import Organization
from app.models.employee import Employee
from app.models.projects import TimesheetPolicy
from app.schemas.projects import (
    TimesheetPolicyCreate, TimesheetPolicyUpdate, TimesheetPolicySchema,
    TimesheetPolicyResponse, TimesheetPolicyListResponse
)

router = APIRouter()


def _require(db, user, code, action):
    if isinstance(user, Organization):
        return
    if not deps.has_permission(db, user, code):
        raise HTTPException(status_code=403, detail=f"No permission to {action} timesheet policies (code: {code})")


def _org_id(user):
    return user.id if isinstance(user, Organization) else user.organization_id


# -------------------------------------------------------
# LIST — Permission 93
# -------------------------------------------------------
@router.get("/", response_model=TimesheetPolicyListResponse)
def list_policies(
    db: Session = Depends(deps.get_db),
    current_user: Union[Organization, Employee] = Depends(deps.get_current_user),
    is_active: Optional[bool] = Query(None),
    period_type: Optional[str] = Query(None),
    applicable_to: Optional[str] = Query(None),
    search: Optional[str] = Query(None),
    sort_by: Optional[str] = Query("created_at"),
    sort_order: Optional[str] = Query("desc")
):
    _require(db, current_user, "93", "view")
    query = db.query(TimesheetPolicy).filter(
        TimesheetPolicy.organization_id == _org_id(current_user),
        TimesheetPolicy.is_deleted == False
    )
    if is_active is not None:
        query = query.filter(TimesheetPolicy.is_active == is_active)
    if period_type is not None:
        query = query.filter(TimesheetPolicy.period_type == period_type)
    if applicable_to is not None:
        query = query.filter(TimesheetPolicy.applicable_to == applicable_to)
    if search:
        query = query.filter(
            or_(
                TimesheetPolicy.policy_name.ilike(f"%{search}%"),
                TimesheetPolicy.description.ilike(f"%{search}%")
            )
        )

    sort_field_map = {
        "policy_name": TimesheetPolicy.policy_name,
        "period_type": TimesheetPolicy.period_type,
        "applicable_to": TimesheetPolicy.applicable_to,
        "is_active": TimesheetPolicy.is_active,
        "created_at": TimesheetPolicy.created_at
    }
    
    sort_field = sort_field_map.get(sort_by, TimesheetPolicy.created_at)
    if sort_order == "asc":
        query = query.order_by(sort_field.asc())
    else:
        query = query.order_by(sort_field.desc())

    policies = query.all()
    return TimesheetPolicyListResponse(success=True, message="Policies retrieved", data=[TimesheetPolicySchema.model_validate(p) for p in policies])


# -------------------------------------------------------
# GET ACTIVE — open (auth only — for employees to know rules)
# -------------------------------------------------------
@router.get("/active")
def get_active_policy(
    db: Session = Depends(deps.get_db),
    current_user: Union[Organization, Employee] = Depends(deps.get_current_user),
):
    """Returns the default active policy. Open to all authenticated users."""
    policy = db.query(TimesheetPolicy).filter(
        TimesheetPolicy.organization_id == _org_id(current_user),
        TimesheetPolicy.is_active == True,
        TimesheetPolicy.is_default == True,
        TimesheetPolicy.is_deleted == False
    ).first()
    if not policy:
        policy = db.query(TimesheetPolicy).filter(
            TimesheetPolicy.organization_id == _org_id(current_user),
            TimesheetPolicy.is_active == True,
            TimesheetPolicy.is_deleted == False
        ).first()
    if not policy:
        return {"success": True, "message": "No active policy configured", "data": None}
    return {"success": True, "message": "Active policy retrieved", "data": TimesheetPolicySchema.model_validate(policy)}


# -------------------------------------------------------
# GET SINGLE — Permission 93
# -------------------------------------------------------
@router.get("/{policy_uuid}", response_model=TimesheetPolicyResponse)
def get_policy(
    policy_uuid: uuid.UUID,
    db: Session = Depends(deps.get_db),
    current_user: Union[Organization, Employee] = Depends(deps.get_current_user)
):
    _require(db, current_user, "93", "view")
    policy = db.query(TimesheetPolicy).filter(
        TimesheetPolicy.uuid == policy_uuid,
        TimesheetPolicy.organization_id == _org_id(current_user),
        TimesheetPolicy.is_deleted == False
    ).first()
    if not policy:
        raise HTTPException(status_code=404, detail="Timesheet policy not found")
    return TimesheetPolicyResponse(success=True, message="Policy retrieved", data=TimesheetPolicySchema.model_validate(policy))


# -------------------------------------------------------
# CREATE — Permission 93
# -------------------------------------------------------
@router.post("/", response_model=TimesheetPolicyResponse, status_code=status.HTTP_201_CREATED)
def create_policy(
    policy_in: TimesheetPolicyCreate,
    db: Session = Depends(deps.get_db),
    current_user: Union[Organization, Employee] = Depends(deps.get_current_user)
):
    _require(db, current_user, "93", "create")
    org_id = _org_id(current_user)

    # If this is default, unset existing default
    if policy_in.is_default:
        db.query(TimesheetPolicy).filter(
            TimesheetPolicy.organization_id == org_id,
            TimesheetPolicy.is_default == True
        ).update({TimesheetPolicy.is_default: False})

    employee_id = current_user.id if isinstance(current_user, Employee) else None
    policy = TimesheetPolicy(organization_id=org_id, created_by=employee_id, **policy_in.model_dump())
    db.add(policy)
    db.commit()
    db.refresh(policy)
    return TimesheetPolicyResponse(success=True, message="Timesheet policy created", data=TimesheetPolicySchema.model_validate(policy))


# -------------------------------------------------------
# UPDATE — Permission 93
# -------------------------------------------------------
@router.put("/{policy_uuid}", response_model=TimesheetPolicyResponse)
def update_policy(
    policy_uuid: uuid.UUID,
    policy_in: TimesheetPolicyUpdate,
    db: Session = Depends(deps.get_db),
    current_user: Union[Organization, Employee] = Depends(deps.get_current_user)
):
    _require(db, current_user, "93", "update")
    org_id = _org_id(current_user)
    policy = db.query(TimesheetPolicy).filter(
        TimesheetPolicy.uuid == policy_uuid,
        TimesheetPolicy.organization_id == org_id,
        TimesheetPolicy.is_deleted == False
    ).first()
    if not policy:
        raise HTTPException(status_code=404, detail="Policy not found")

    # If setting as default, clear others first
    if policy_in.is_default:
        db.query(TimesheetPolicy).filter(
            TimesheetPolicy.organization_id == org_id,
            TimesheetPolicy.is_default == True,
            TimesheetPolicy.id != policy.id
        ).update({TimesheetPolicy.is_default: False})

    for field, value in policy_in.model_dump(exclude_unset=True).items():
        setattr(policy, field, value)
    db.commit()
    db.refresh(policy)
    return TimesheetPolicyResponse(success=True, message="Policy updated", data=TimesheetPolicySchema.model_validate(policy))


# -------------------------------------------------------
# DELETE — Permission 93
# -------------------------------------------------------
@router.delete("/{policy_uuid}")
def delete_policy(
    policy_uuid: uuid.UUID,
    db: Session = Depends(deps.get_db),
    current_user: Union[Organization, Employee] = Depends(deps.get_current_user)
):
    _require(db, current_user, "93", "delete")
    policy = db.query(TimesheetPolicy).filter(
        TimesheetPolicy.uuid == policy_uuid,
        TimesheetPolicy.organization_id == _org_id(current_user),
        TimesheetPolicy.is_deleted == False
    ).first()
    if not policy:
        raise HTTPException(status_code=404, detail="Policy not found")
    policy.is_deleted = True
    policy.is_active = False
    db.commit()
    return {"success": True, "message": "Policy deleted"}
