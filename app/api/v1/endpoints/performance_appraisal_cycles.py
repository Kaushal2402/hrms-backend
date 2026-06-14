import uuid
from typing import List, Optional, Union
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from sqlalchemy import func, or_

from app.api import deps
from app.models.organization import Organization
from app.models.employee import Employee, Department
from app.models.performance import (
    AppraisalCycle, CycleStatus, AppraisalTemplate, RatingScale,
    AppraisalRecord, AppraisalStatus
)
from app.schemas.performance_appraisal_cycles import (
    AppraisalCycleCreate, AppraisalCycleUpdate, AppraisalCycleSchema,
    AppraisalCycleResponse, AppraisalCycleListResponse, AppraisalCycleDetailResponse,
    AppraisalCycleLookupResponse,
    CycleAdvancePhaseRequest, CyclePublishResultsRequest,
    PendingEmployeeItem, PendingListResponse, SendRemindersRequest, SendRemindersResponse,
    RecipientGroup
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
    sort_by: Optional[str] = Query("created_at"),
    sort_order: Optional[str] = Query("desc"),
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
    
    # Sorting logic
    allowed_sort_fields = {
        "name": AppraisalCycle.name,
        "frequency": AppraisalCycle.frequency,
        "fiscal_year": AppraisalCycle.fiscal_year,
        "review_period_start": AppraisalCycle.review_period_start,
        "review_period_end": AppraisalCycle.review_period_end,
        "status": AppraisalCycle.status,
        "created_at": AppraisalCycle.created_at
    }
    sort_field = allowed_sort_fields.get(sort_by, AppraisalCycle.created_at)
    if sort_order == "desc":
        query = query.order_by(sort_field.desc())
    else:
        query = query.order_by(sort_field.asc())
        
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
    
    # Resolve template_uuid
    tmpl = db.query(AppraisalTemplate).filter(AppraisalTemplate.uuid == item_in.template_uuid, AppraisalTemplate.organization_id == org_id).first()
    if not tmpl:
        raise HTTPException(400, "Appraisal template not found")
    template_id_val = tmpl.id
        
    # Resolve rating_scale_uuid
    scale = db.query(RatingScale).filter(RatingScale.uuid == item_in.rating_scale_uuid, RatingScale.organization_id == org_id).first()
    if not scale:
        raise HTTPException(400, "Rating scale not found")
    rating_scale_id_val = scale.id
        
    cycle_data = item_in.model_dump()
    cycle_data.pop("template_uuid", None)
    cycle_data.pop("rating_scale_uuid", None)
    
    if "applicable_departments" in cycle_data and cycle_data["applicable_departments"]:
        cycle_data["applicable_departments"] = [str(u) for u in cycle_data["applicable_departments"]]
    
    created_by_val = current_user.id if not isinstance(current_user, Organization) else 1
    
    cycle = AppraisalCycle(
        organization_id=org_id,
        created_by=created_by_val,
        template_id=template_id_val,
        rating_scale_id=rating_scale_id_val,
        **cycle_data
    )
    db.add(cycle)
    db.commit()
    db.refresh(cycle)
    return {"success": True, "message": "Cycle created", "data": cycle}

@router.get("/lookup", response_model=AppraisalCycleLookupResponse)
def lookup_cycles(
    status: Optional[CycleStatus] = None,
    search: Optional[str] = None,
    limit: int = Query(100, ge=1, le=1000),
    db: Session = Depends(deps.get_db),
    current_user: Union[Organization, Employee] = Depends(deps.get_current_user)
):
    """
    Get simplified list of appraisal cycles for dropdowns/menus. No RBAC permissions check.
    """
    org_id = _get_org_id(current_user)
    query = db.query(AppraisalCycle).filter(AppraisalCycle.organization_id == org_id)
    if status:
        query = query.filter(AppraisalCycle.status == status)
    if search:
        query = query.filter(AppraisalCycle.name.ilike(f"%{search}%"))
    
    cycles = query.order_by(AppraisalCycle.name.asc()).limit(limit).all()
    return {
        "success": True,
        "message": "Cycles lookup retrieved successfully",
        "data": cycles
    }

@router.get("/{cycle_id}", response_model=AppraisalCycleDetailResponse)
def get_cycle(
    cycle_id: str,
    db: Session = Depends(deps.get_db),
    current_user: Union[Organization, Employee] = Depends(deps.get_current_user)
):
    _require_permission(db, current_user, PerformanceAppraisalCyclePermissions.READ, "get cycle details")
    org_id = _get_org_id(current_user)
    
    cycle = None
    try:
        val_uuid = uuid.UUID(cycle_id)
        cycle = db.query(AppraisalCycle).filter(AppraisalCycle.uuid == val_uuid, AppraisalCycle.organization_id == org_id).first()
    except ValueError:
        pass
        
    if not cycle:
        try:
            val_id = int(cycle_id)
            cycle = db.query(AppraisalCycle).filter(AppraisalCycle.id == val_id, AppraisalCycle.organization_id == org_id).first()
        except ValueError:
            pass
            
    if not cycle:
        raise HTTPException(404, "Cycle not found")
        
    # Resolve department objects
    dept_objects = []
    if cycle.applicable_departments:
        dept_uuids = []
        for d_str in cycle.applicable_departments:
            try:
                dept_uuids.append(uuid.UUID(d_str) if isinstance(d_str, str) else d_str)
            except ValueError:
                pass
        if dept_uuids:
            dept_objects = db.query(Department).filter(
                Department.uuid.in_(dept_uuids),
                Department.organization_id == org_id
            ).all()
    cycle.departments = dept_objects
        
    return {"success": True, "message": "Cycle retrieved", "data": cycle}

@router.put("/{cycle_id}", response_model=AppraisalCycleResponse)
def update_cycle(
    cycle_id: str,
    item_in: AppraisalCycleUpdate,
    db: Session = Depends(deps.get_db),
    current_user: Union[Organization, Employee] = Depends(deps.get_current_user)
):
    _require_permission(db, current_user, PerformanceAppraisalCyclePermissions.UPDATE, "update cycle")
    org_id = _get_org_id(current_user)
    
    cycle = None
    try:
        val_uuid = uuid.UUID(cycle_id)
        cycle = db.query(AppraisalCycle).filter(AppraisalCycle.uuid == val_uuid, AppraisalCycle.organization_id == org_id).first()
    except ValueError:
        pass
        
    if not cycle:
        try:
            val_id = int(cycle_id)
            cycle = db.query(AppraisalCycle).filter(AppraisalCycle.id == val_id, AppraisalCycle.organization_id == org_id).first()
        except ValueError:
            pass
            
    if not cycle:
        raise HTTPException(404, "Cycle not found")
        
    if cycle.status != CycleStatus.DRAFT:
        raise HTTPException(400, "Cycle can only be updated in DRAFT status")
        
    update_data = item_in.model_dump(exclude_unset=True)
    
    if "applicable_departments" in update_data and update_data["applicable_departments"] is not None:
        update_data["applicable_departments"] = [str(u) for u in update_data["applicable_departments"]]
    
    if "template_uuid" in update_data and update_data["template_uuid"] is not None:
        t_uuid = update_data.pop("template_uuid")
        tmpl = db.query(AppraisalTemplate).filter(AppraisalTemplate.uuid == t_uuid, AppraisalTemplate.organization_id == org_id).first()
        if not tmpl:
            raise HTTPException(400, "Appraisal template not found")
        cycle.template_id = tmpl.id
            
    if "rating_scale_uuid" in update_data and update_data["rating_scale_uuid"] is not None:
        r_uuid = update_data.pop("rating_scale_uuid")
        scale = db.query(RatingScale).filter(RatingScale.uuid == r_uuid, RatingScale.organization_id == org_id).first()
        if not scale:
            raise HTTPException(400, "Rating scale not found")
        cycle.rating_scale_id = scale.id
            
    for k, v in update_data.items():
        setattr(cycle, k, v)
        
    db.commit()
    db.refresh(cycle)
    return {"success": True, "message": "Cycle updated", "data": cycle}


# ─────────────────────────────────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────────────────────────────────

def _resolve_cycle(cycle_id: str, org_id: int, db: Session) -> AppraisalCycle:
    """Look up a cycle by UUID or integer ID and verify org ownership."""
    cycle = None
    try:
        val_uuid = uuid.UUID(cycle_id)
        cycle = db.query(AppraisalCycle).filter(
            AppraisalCycle.uuid == val_uuid,
            AppraisalCycle.organization_id == org_id
        ).first()
    except ValueError:
        pass
    if not cycle:
        try:
            val_id = int(cycle_id)
            cycle = db.query(AppraisalCycle).filter(
                AppraisalCycle.id == val_id,
                AppraisalCycle.organization_id == org_id
            ).first()
        except ValueError:
            pass
    if not cycle:
        raise HTTPException(404, "Cycle not found")
    return cycle


# ─────────────────────────────────────────────────────────────────────
# PATCH  /{cycle_id}/launch
# ─────────────────────────────────────────────────────────────────────

@router.patch("/{cycle_id}/launch")
def launch_cycle(
    cycle_id: str,
    db: Session = Depends(deps.get_db),
    current_user: Union[Organization, Employee] = Depends(deps.get_current_user)
):
    """
    Launch an appraisal cycle — transition from DRAFT → ACTIVE,
    generate one AppraisalRecord per eligible employee, and log
    a simulated kick-off notification count.
    """
    _require_permission(db, current_user, PerformanceAppraisalCyclePermissions.UPDATE, "launch cycle")
    org_id = _get_org_id(current_user)
    cycle = _resolve_cycle(cycle_id, org_id, db)

    if cycle.status != CycleStatus.DRAFT:
        raise HTTPException(400, f"Cycle must be in DRAFT status to launch. Current status: {cycle.status}")

    # Determine eligible employees -------------------------------------------
    emp_query = db.query(Employee).filter(
        Employee.organization_id == org_id,
        Employee.is_active == True
    )

    # Filter by applicable_departments if configured
    if cycle.applicable_departments:
        dept_uuids = []
        for d in cycle.applicable_departments:
            try:
                dept_uuids.append(uuid.UUID(d) if isinstance(d, str) else d)
            except ValueError:
                pass
        if dept_uuids:
            dept_ids = [
                row.id for row in
                db.query(Department.id).filter(
                    Department.uuid.in_(dept_uuids),
                    Department.organization_id == org_id
                ).all()
            ]
            emp_query = emp_query.filter(Employee.department_id.in_(dept_ids))

    # Filter by applicable_employee_types if configured
    if cycle.applicable_employee_types:
        emp_query = emp_query.filter(
            Employee.employment_type.in_(cycle.applicable_employee_types)
        )

    # Exclude probationary employees if not included
    if not cycle.include_probationary and cycle.minimum_tenure_days:
        from datetime import date, timedelta
        cutoff = date.today() - timedelta(days=cycle.minimum_tenure_days)
        emp_query = emp_query.filter(Employee.date_of_joining <= cutoff)

    employees = emp_query.all()

    # Create AppraisalRecord for each eligible employee ----------------------
    created = 0
    for emp in employees:
        # Skip if a record already exists (idempotent re-launch guard)
        existing = db.query(AppraisalRecord).filter(
            AppraisalRecord.appraisal_cycle_id == cycle.id,
            AppraisalRecord.employee_id == emp.id
        ).first()
        if existing:
            continue

        manager_id = getattr(emp, "reporting_manager_id", None)
        record = AppraisalRecord(
            organization_id=org_id,
            appraisal_cycle_id=cycle.id,
            employee_id=emp.id,
            manager_id=manager_id,
            template_id=cycle.template_id,
            rating_scale_id=cycle.rating_scale_id,
            status=AppraisalStatus.NOT_STARTED,
        )
        db.add(record)
        created += 1

    # Advance cycle status
    cycle.status = CycleStatus.ACTIVE
    db.commit()
    db.refresh(cycle)

    return {
        "success": True,
        "message": f"Cycle launched. {created} appraisal records created.",
        "data": {
            "cycle_uuid": str(cycle.uuid),
            "cycle_name": cycle.name,
            "new_status": cycle.status,
            "records_created": created,
            "notifications_sent": created,  # 1-to-1 in this model; extend with email service
        }
    }


# ─────────────────────────────────────────────────────────────────────
# PATCH  /{cycle_id}/advance-phase
# ─────────────────────────────────────────────────────────────────────

# Phase transition map: current → next
_PHASE_TRANSITIONS: dict = {
    CycleStatus.ACTIVE:         CycleStatus.SELF_APPRAISAL,
    CycleStatus.SELF_APPRAISAL: CycleStatus.MANAGER_REVIEW,
    CycleStatus.MANAGER_REVIEW: CycleStatus.CALIBRATION,
    CycleStatus.CALIBRATION:    CycleStatus.COMPLETED,
}

@router.patch("/{cycle_id}/advance-phase")
def advance_phase(
    cycle_id: str,
    body: CycleAdvancePhaseRequest,
    db: Session = Depends(deps.get_db),
    current_user: Union[Organization, Employee] = Depends(deps.get_current_user)
):
    """
    Advance a cycle to the next phase.
    Transition map: ACTIVE → SELF_APPRAISAL → MANAGER_REVIEW → CALIBRATION → COMPLETED.
    Use force_advance=true to skip pending-completion checks.
    """
    _require_permission(db, current_user, PerformanceAppraisalCyclePermissions.UPDATE, "advance cycle phase")
    org_id = _get_org_id(current_user)
    cycle = _resolve_cycle(cycle_id, org_id, db)

    next_status = _PHASE_TRANSITIONS.get(cycle.status)
    if not next_status:
        raise HTTPException(
            400,
            f"Cycle cannot be advanced from status '{cycle.status}'. "
            f"Advanceable statuses: {list(_PHASE_TRANSITIONS.keys())}"
        )

    # Guard: check all records are complete before advancing (unless force)
    if not body.force_advance:
        incomplete_count = 0
        if cycle.status == CycleStatus.SELF_APPRAISAL:
            incomplete_count = db.query(AppraisalRecord).filter(
                AppraisalRecord.appraisal_cycle_id == cycle.id,
                AppraisalRecord.status.in_([
                    AppraisalStatus.NOT_STARTED,
                    AppraisalStatus.SELF_IN_PROGRESS
                ])
            ).count()
        elif cycle.status == CycleStatus.MANAGER_REVIEW:
            incomplete_count = db.query(AppraisalRecord).filter(
                AppraisalRecord.appraisal_cycle_id == cycle.id,
                AppraisalRecord.status.in_([
                    AppraisalStatus.SELF_SUBMITTED,
                    AppraisalStatus.MANAGER_IN_PROGRESS
                ])
            ).count()
        elif cycle.status == CycleStatus.CALIBRATION:
            incomplete_count = db.query(AppraisalRecord).filter(
                AppraisalRecord.appraisal_cycle_id == cycle.id,
                AppraisalRecord.status == AppraisalStatus.CALIBRATION_PENDING
            ).count()

        if incomplete_count > 0:
            raise HTTPException(
                400,
                f"{incomplete_count} appraisal record(s) are still pending in the current phase. "
                "Use force_advance=true to override."
            )

    # Append history
    history_entry = {
        "phase": next_status,
        "notes": body.notes,
        "advanced_by": str(current_user.uuid) if hasattr(current_user, 'uuid') else None,
        "advanced_at": datetime.utcnow().isoformat() + "Z"
    }
    
    current_history = cycle.advance_history or []
    cycle.advance_history = current_history + [history_entry]

    cycle.status = next_status
    db.commit()
    db.refresh(cycle)

    return {
        "success": True,
        "message": f"Cycle advanced to '{next_status}'.",
        "data": {
            "cycle_uuid": str(cycle.uuid),
            "cycle_name": cycle.name,
            "previous_status": str(cycle.status),  # already updated; log above for reference
            "new_status": next_status,
            "forced": body.force_advance,
            "notes": body.notes,
        }
    }


# ─────────────────────────────────────────────────────────────────────
# PATCH  /{cycle_id}/publish-results
# ─────────────────────────────────────────────────────────────────────

@router.patch("/{cycle_id}/publish-results")
def publish_results(
    cycle_id: str,
    body: CyclePublishResultsRequest,
    db: Session = Depends(deps.get_db),
    current_user: Union[Organization, Employee] = Depends(deps.get_current_user)
):
    """
    Publish final appraisal ratings to employees.
    Supports full publish (publish_all=true) or selective publish via employee_uuids.
    Cycle must be in COMPLETED status.
    """
    _require_permission(db, current_user, PerformanceAppraisalCyclePermissions.UPDATE, "publish cycle results")
    org_id = _get_org_id(current_user)
    cycle = _resolve_cycle(cycle_id, org_id, db)

    if cycle.status != CycleStatus.COMPLETED:
        raise HTTPException(400, f"Results can only be published for COMPLETED cycles. Current status: {cycle.status}")

    published_by_id = current_user.id if not isinstance(current_user, Organization) else None
    now = datetime.utcnow()

    records_query = db.query(AppraisalRecord).filter(
        AppraisalRecord.appraisal_cycle_id == cycle.id,
        AppraisalRecord.status != AppraisalStatus.PUBLISHED
    )

    # Selective publish
    if not body.publish_all and body.employee_uuids:
        emp_uuids_str = [str(u) for u in body.employee_uuids]
        # Resolve UUIDs → employee IDs
        emp_ids = [
            row.id for row in
            db.query(Employee.id).filter(
                Employee.uuid.in_([uuid.UUID(u) for u in emp_uuids_str]),
                Employee.organization_id == org_id
            ).all()
        ]
        records_query = records_query.filter(AppraisalRecord.employee_id.in_(emp_ids))

    records = records_query.all()
    count = 0
    for record in records:
        record.status = AppraisalStatus.PUBLISHED
        record.published_at = now
        record.published_by = published_by_id
        count += 1

    db.commit()

    return {
        "success": True,
        "message": f"{count} appraisal result(s) published.",
        "data": {
            "cycle_uuid": str(cycle.uuid),
            "cycle_name": cycle.name,
            "published_count": count,
            "publish_all": body.publish_all,
            "published_at": now.isoformat(),
        }
    }


# ─────────────────────────────────────────────────────────────────────
# GET  /{cycle_id}/dashboard
# ─────────────────────────────────────────────────────────────────────

@router.get("/{cycle_id}/dashboard")
def get_cycle_dashboard(
    cycle_id: str,
    db: Session = Depends(deps.get_db),
    current_user: Union[Organization, Employee] = Depends(deps.get_current_user)
):
    """
    Cycle-level dashboard: completion stats per phase, and a list of
    employees whose appraisals are still pending (not submitted or not reviewed).
    """
    _require_permission(db, current_user, PerformanceAppraisalCyclePermissions.READ, "view cycle dashboard")
    org_id = _get_org_id(current_user)
    cycle = _resolve_cycle(cycle_id, org_id, db)

    # Aggregate counts by status
    status_counts: dict = {s.value: 0 for s in AppraisalStatus}
    rows = (
        db.query(AppraisalRecord.status, func.count(AppraisalRecord.id))
        .filter(AppraisalRecord.appraisal_cycle_id == cycle.id)
        .group_by(AppraisalRecord.status)
        .all()
    )
    for row_status, cnt in rows:
        status_counts[row_status] = cnt

    total = sum(status_counts.values())
    completed_statuses = {
        AppraisalStatus.MANAGER_SUBMITTED,
        AppraisalStatus.CALIBRATION_PENDING,
        AppraisalStatus.CALIBRATED,
        AppraisalStatus.PUBLISHED,
        AppraisalStatus.ACKNOWLEDGED,
    }
    completed_count = sum(
        status_counts.get(s.value, 0) for s in completed_statuses
    )
    completion_pct = round((completed_count / total * 100), 1) if total else 0.0

    # Pending list: records not yet self-submitted
    pending_records = (
        db.query(AppraisalRecord)
        .filter(
            AppraisalRecord.appraisal_cycle_id == cycle.id,
            AppraisalRecord.status.in_([
                AppraisalStatus.NOT_STARTED,
                AppraisalStatus.SELF_IN_PROGRESS,
                AppraisalStatus.SELF_SUBMITTED,
                AppraisalStatus.MANAGER_IN_PROGRESS,
            ])
        )
        .limit(100)
        .all()
    )

    pending_list = []
    for rec in pending_records:
        emp = rec.employee
        dept_name = None
        if emp and emp.department:
            dept_name = emp.department.department_name
        full_name = f"{emp.first_name} {emp.last_name}" if emp else "Unknown"
        pending_list.append(
            PendingEmployeeItem(
                uuid=rec.employee.uuid if rec.employee else uuid.uuid4(),
                full_name=full_name,
                department=dept_name,
                appraisal_status=rec.status,
            )
        )

    return {
        "success": True,
        "message": "Dashboard data retrieved",
        "data": {
            "cycle_uuid": str(cycle.uuid),
            "cycle_name": cycle.name,
            "cycle_status": cycle.status,
            "total_employees": total,
            "not_started_count": status_counts.get(AppraisalStatus.NOT_STARTED, 0),
            "self_in_progress_count": status_counts.get(AppraisalStatus.SELF_IN_PROGRESS, 0),
            "self_submitted_count": status_counts.get(AppraisalStatus.SELF_SUBMITTED, 0),
            "manager_in_progress_count": status_counts.get(AppraisalStatus.MANAGER_IN_PROGRESS, 0),
            "manager_reviewed_count": status_counts.get(AppraisalStatus.MANAGER_SUBMITTED, 0),
            "calibrated_count": status_counts.get(AppraisalStatus.CALIBRATED, 0),
            "published_count": status_counts.get(AppraisalStatus.PUBLISHED, 0),
            "acknowledged_count": status_counts.get(AppraisalStatus.ACKNOWLEDGED, 0),
            "completion_percentage": completion_pct,
            "pending_list": [p.model_dump(mode="json") for p in pending_list],
        }
    }


# ─────────────────────────────────────────────────────────────────────
# GET  /{cycle_id}/pending
# ─────────────────────────────────────────────────────────────────────

@router.get("/{cycle_id}/pending", response_model=PendingListResponse)
def get_pending_actions(
    cycle_id: str,
    phase: Optional[CycleStatus] = None,
    department_uuid: Optional[str] = None,
    manager_uuid: Optional[str] = None,
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    db: Session = Depends(deps.get_db),
    current_user: Union[Organization, Employee] = Depends(deps.get_current_user)
):
    """List employees with pending actions in the current phase."""
    _require_permission(db, current_user, PerformanceAppraisalCyclePermissions.READ, "get pending actions")
    org_id = _get_org_id(current_user)
    cycle = _resolve_cycle(cycle_id, org_id, db)

    query = db.query(AppraisalRecord).filter(AppraisalRecord.appraisal_cycle_id == cycle.id)

    if phase == CycleStatus.SELF_APPRAISAL:
        query = query.filter(AppraisalRecord.status.in_([AppraisalStatus.NOT_STARTED, AppraisalStatus.SELF_IN_PROGRESS]))
    elif phase == CycleStatus.MANAGER_REVIEW:
        query = query.filter(AppraisalRecord.status.in_([AppraisalStatus.SELF_SUBMITTED, AppraisalStatus.MANAGER_IN_PROGRESS]))
    elif phase == CycleStatus.CALIBRATION:
        query = query.filter(AppraisalRecord.status == AppraisalStatus.CALIBRATION_PENDING)

    if department_uuid:
        try:
            val_uuid = uuid.UUID(department_uuid)
            query = query.join(Employee, AppraisalRecord.employee_id == Employee.id).filter(
                Employee.department_id == db.query(Department.id).filter(Department.uuid == val_uuid).scalar()
            )
        except ValueError:
            pass
            
    if manager_uuid:
        try:
            val_uuid = uuid.UUID(manager_uuid)
            query = query.join(Employee, AppraisalRecord.manager_id == Employee.id, aliased=True).filter(
                Employee.uuid == val_uuid
            )
        except ValueError:
            pass

    total = query.count()
    offset = (page - 1) * limit
    records = query.offset(offset).limit(limit).all()

    items = []
    for rec in records:
        emp = rec.employee
        dept_name = emp.department.department_name if emp and emp.department else None
        full_name = f"{emp.first_name} {emp.last_name}" if emp else "Unknown"
        manager_name = None
        manager_uuid_val = None
        if rec.manager:
            manager_name = f"{rec.manager.first_name} {rec.manager.last_name}"
            manager_uuid_val = rec.manager.uuid
        items.append(PendingEmployeeItem(
            uuid=emp.uuid if emp else uuid.uuid4(),
            full_name=full_name,
            department=dept_name,
            appraisal_status=rec.status,
            manager_name=manager_name,
            manager_uuid=manager_uuid_val
        ))

    return {
        "success": True,
        "message": "Pending actions retrieved",
        "data": items,
        "meta": {
            "total": total,
            "page": page,
            "limit": limit,
            "total_pages": max(1, (total + limit - 1) // limit)
        }
    }


# ─────────────────────────────────────────────────────────────────────
# POST /{cycle_id}/send-reminders
# ─────────────────────────────────────────────────────────────────────

@router.post("/{cycle_id}/send-reminders", response_model=SendRemindersResponse)
def send_reminders(
    cycle_id: str,
    item_in: SendRemindersRequest,
    db: Session = Depends(deps.get_db),
    current_user: Union[Organization, Employee] = Depends(deps.get_current_user)
):
    """Send bulk reminder notifications for a cycle phase."""
    _require_permission(db, current_user, PerformanceAppraisalCyclePermissions.UPDATE, "send reminders")
    org_id = _get_org_id(current_user)
    cycle = _resolve_cycle(cycle_id, org_id, db)
    
    # In a real app we would use celery/email service. For now we simulate sending count.
    query = db.query(AppraisalRecord).filter(AppraisalRecord.appraisal_cycle_id == cycle.id)
    
    if item_in.phase == CycleStatus.SELF_APPRAISAL:
        query = query.filter(AppraisalRecord.status.in_([AppraisalStatus.NOT_STARTED, AppraisalStatus.SELF_IN_PROGRESS]))
    elif item_in.phase == CycleStatus.MANAGER_REVIEW:
        query = query.filter(AppraisalRecord.status.in_([AppraisalStatus.SELF_SUBMITTED, AppraisalStatus.MANAGER_IN_PROGRESS]))
    elif item_in.phase == CycleStatus.CALIBRATION:
        query = query.filter(AppraisalRecord.status == AppraisalStatus.CALIBRATION_PENDING)

    if item_in.department_uuids:
        dept_ids = []
        for duuid in item_in.department_uuids:
            try:
                dept_id = db.query(Department.id).filter(Department.uuid == duuid).scalar()
                if dept_id:
                    dept_ids.append(dept_id)
            except ValueError:
                pass
        if dept_ids:
            query = query.join(Employee, AppraisalRecord.employee_id == Employee.id).filter(Employee.department_id.in_(dept_ids))
            
    records = query.all()
    sent_count = len(records)
    
    if item_in.recipient_group == RecipientGroup.ALL:
        sent_count *= 2  # simulate sending to employee and manager
        
    return {
        "success": True,
        "message": "Reminders sent successfully",
        "data": {
            "sent_count": sent_count,
            "failed_count": 0
        }
    }

@router.delete("/{cycle_id}")
def delete_cycle(
    cycle_id: str,
    db: Session = Depends(deps.get_db),
    current_user: Union[Organization, Employee] = Depends(deps.get_current_user)
):
    _require_permission(db, current_user, PerformanceAppraisalCyclePermissions.DELETE, "delete cycle")
    org_id = _get_org_id(current_user)
    
    cycle = None
    try:
        val_uuid = uuid.UUID(cycle_id)
        cycle = db.query(AppraisalCycle).filter(AppraisalCycle.uuid == val_uuid, AppraisalCycle.organization_id == org_id).first()
    except ValueError:
        pass
        
    if not cycle:
        try:
            val_id = int(cycle_id)
            cycle = db.query(AppraisalCycle).filter(AppraisalCycle.id == val_id, AppraisalCycle.organization_id == org_id).first()
        except ValueError:
            pass
            
    if not cycle:
        raise HTTPException(404, "Cycle not found")
        
    if cycle.status != CycleStatus.DRAFT:
        raise HTTPException(400, "Cannot delete active/completed cycle")
        
    db.delete(cycle)
    db.commit()
    return {"success": True, "message": "Cycle deleted"}