import uuid
from typing import List, Optional, Union
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from sqlalchemy import func, or_

from app.api import deps
from app.models.organization import Organization
from app.models.employee import Employee
from app.models.performance import AppraisalCycle, CycleStatus
from app.schemas.performance_appraisal_cycles import (
    AppraisalCycleCreate, AppraisalCycleUpdate, AppraisalCycleSchema,
    AppraisalCycleResponse, AppraisalCycleListResponse
)
from app.core.permissions import PerformanceAppraisalCyclePermissions

router = APIRouter()

def _get_org_id(current_user: Union[Organization, Employee]) -> int:
    return current_user.id if isinstance(current_user, Organization) else current_user.organization_id

def _require_permission(db: Session, current_user: Union[Organization, Employee], code: str, action: str):
    if not isinstance(current_user, Organization) and not deps.has_permission(db, current_user, code):
        raise HTTPException(status_code=403, detail=f"Permission denied: {action}")

@router.get("/", response_model=AppraisalCycleListResponse)
def get_cycles(
    status: Optional[CycleStatus] = None,
    frequency: Optional[str] = None,
    fiscal_year: Optional[str] = None,
    page: int = Query(1, ge=1),
    limit: int = Query(10, ge=1, le=100),
    search: Optional[str] = None,
    db: Session = Depends(deps.get_db),
    current_user: Union[Organization, Employee] = Depends(deps.get_current_user)
):
    _require_permission(db, current_user, PerformanceAppraisalCyclePermissions.READ, "list cycles")
    org_id = _get_org_id(current_user)
    query = db.query(AppraisalCycle).filter(AppraisalCycle.organization_id == org_id)
    
    if status: query = query.filter(AppraisalCycle.status == status)
    if frequency: query = query.filter(AppraisalCycle.frequency == frequency)
    if fiscal_year: query = query.filter(AppraisalCycle.fiscal_year == fiscal_year)
    if search: query = query.filter(AppraisalCycle.name.ilike(f"%{search}%"))
    
    total = query.count()
    items = query.offset((page - 1) * limit).limit(limit).all()
    return AppraisalCycleListResponse(
        success=True, message="Cycles retrieved", data=items,
        pagination={"total_records": total, "current_page": page, "total_pages": (total + limit - 1) // limit, "page_size": limit}
    )

@router.post("/", response_model=AppraisalCycleResponse)
def create_cycle(
    item_in: AppraisalCycleCreate,
    db: Session = Depends(deps.get_db),
    current_user: Union[Organization, Employee] = Depends(deps.get_current_user)
):
    _require_permission(db, current_user, PerformanceAppraisalCyclePermissions.CREATE, "create cycle")
    if item_in.review_period_start >= item_in.review_period_end:
        raise HTTPException(400, "Invalid review period dates")
    
    org_id = _get_org_id(current_user)
    cycle = AppraisalCycle(organization_id=org_id, **item_in.model_dump(), created_by=current_user.id if not isinstance(current_user, Organization) else 1)
    db.add(cycle); db.commit(); db.refresh(cycle)
    return {"success": True, "message": "Cycle created", "data": cycle}

@router.get("/{cycle_uuid}", response_model=AppraisalCycleResponse)
def get_cycle(cycle_uuid: uuid.UUID, db: Session = Depends(deps.get_db), current_user: Union[Organization, Employee] = Depends(deps.get_current_user)):
    org_id = _get_org_id(current_user)
    cycle = db.query(AppraisalCycle).filter(AppraisalCycle.uuid == cycle_uuid, AppraisalCycle.organization_id == org_id).first()
    if not cycle: raise HTTPException(404, "Cycle not found")
    return {"success": True, "message": "Cycle retrieved", "data": cycle}

@router.put("/{cycle_uuid}", response_model=AppraisalCycleResponse)
def update_cycle(cycle_uuid: uuid.UUID, item_in: AppraisalCycleUpdate, db: Session = Depends(deps.get_db), current_user: Union[Organization, Employee] = Depends(deps.get_current_user)):
    _require_permission(db, current_user, PerformanceAppraisalCyclePermissions.UPDATE, "update cycle")
    org_id = _get_org_id(current_user)
    cycle = db.query(AppraisalCycle).filter(AppraisalCycle.uuid == cycle_uuid, AppraisalCycle.organization_id == org_id).first()
    if not cycle or cycle.status != CycleStatus.DRAFT: raise HTTPException(400, "Cycle not found or not in DRAFT")
    for k, v in item_in.model_dump(exclude_unset=True).items(): setattr(cycle, k, v)
    db.commit(); db.refresh(cycle)
    return {"success": True, "message": "Cycle updated", "data": cycle}

@router.delete("/{cycle_uuid}")
def delete_cycle(cycle_uuid: uuid.UUID, db: Session = Depends(deps.get_db), current_user: Union[Organization, Employee] = Depends(deps.get_current_user)):
    _require_permission(db, current_user, PerformanceAppraisalCyclePermissions.DELETE, "delete cycle")
    org_id = _get_org_id(current_user)
    cycle = db.query(AppraisalCycle).filter(AppraisalCycle.uuid == cycle_uuid, AppraisalCycle.organization_id == org_id).first()
    if not cycle or cycle.status != CycleStatus.DRAFT: raise HTTPException(400, "Cannot delete active/completed cycle")
    db.delete(cycle); db.commit()
    return {"success": True, "message": "Cycle deleted"}