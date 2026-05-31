import uuid
from typing import List, Optional, Union
from decimal import Decimal
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from sqlalchemy import or_, and_

from app.api import deps
from app.models.organization import Organization
from app.models.employee import Employee
from app.models.performance import OrganizationGoal, GoalFramework, DepartmentGoal, EmployeeGoal, GoalStatus, GoalFrameworkType
from app.schemas.performance_org_goals import (
    OrgGoalCreate, OrgGoalUpdate, OrgGoalStatusUpdate, OrgGoalSchema,
    OrgGoalResponse, OrgGoalListResponse, OrgGoalSummaryResponse,
    OrgGoalSummarySchema, GoalCascadeItem, GoalCascadeResponse
)

router = APIRouter()

class PerformancePermissions:
    READ = "205"
    CREATE = "206"
    UPDATE = "207"
    DELETE = "208"

def _get_org_id(current_user: Union[Organization, Employee]) -> int:
    return current_user.id if isinstance(current_user, Organization) else current_user.organization_id

def _require_permission(db: Session, current_user: Union[Organization, Employee], code: str, action_label: str):
    if isinstance(current_user, Organization):
        return
    if not deps.has_permission(db, current_user, code):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=f"You do not have permission to {action_label}")

def _is_manager(db: Session, employee_id: int) -> bool:
    # Check if this employee manages anyone
    return db.query(Employee).filter(Employee.manager_id == employee_id).first() is not None

def _calculate_progress(current_val: Optional[Decimal], target_val: Optional[Decimal]) -> Decimal:
    if not target_val or target_val == Decimal("0.00"):
        return Decimal("0.00")
    if current_val is None:
        current_val = Decimal("0.00")
    progress = (current_val / target_val) * Decimal("100.00")
    return min(max(progress, Decimal("0.00")), Decimal("100.00"))

def _resolve_ids(db: Session, org_id: int, payload) -> tuple[int, int]:
    # Resolve framework_id (which could be int or UUID as string/UUID4)
    framework_val = getattr(payload, "framework_id", None)
    framework_id = None
    if framework_val is not None:
        if isinstance(framework_val, int):
            f_obj = db.query(GoalFramework).filter(GoalFramework.id == framework_val, GoalFramework.organization_id == org_id).first()
        else:
            # Try UUID or name/string
            try:
                val_uuid = uuid.UUID(str(framework_val))
                f_obj = db.query(GoalFramework).filter(GoalFramework.uuid == val_uuid, GoalFramework.organization_id == org_id).first()
            except ValueError:
                f_obj = db.query(GoalFramework).filter(GoalFramework.name == str(framework_val), GoalFramework.organization_id == org_id).first()
        if not f_obj:
            raise HTTPException(status_code=404, detail=f"Goal framework '{framework_val}' not found")
        framework_id = f_obj.id

    # Resolve owner_id
    owner_val = getattr(payload, "owner_id", None)
    owner_id = None
    if owner_val is not None:
        if isinstance(owner_val, int):
            o_obj = db.query(Employee).filter(Employee.id == owner_val, Employee.organization_id == org_id).first()
        else:
            try:
                val_uuid = uuid.UUID(str(owner_val))
                o_obj = db.query(Employee).filter(Employee.uuid == val_uuid, Employee.organization_id == org_id).first()
            except ValueError:
                o_obj = db.query(Employee).filter(Employee.email == str(owner_val), Employee.organization_id == org_id).first()
        if not o_obj:
            raise HTTPException(status_code=404, detail=f"Owner employee '{owner_val}' not found")
        owner_id = o_obj.id

    return framework_id, owner_id

@router.get("/", response_model=OrgGoalListResponse)
def list_org_goals(
    fiscal_year: Optional[str] = None,
    status_filter: Optional[GoalStatus] = Query(None, alias="status"),
    framework_type: Optional[GoalFrameworkType] = None,
    framework_id: Optional[str] = None,
    owner_id: Optional[str] = None,
    search: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    limit: int = Query(10, ge=1, le=100),
    db: Session = Depends(deps.get_db),
    current_user: Union[Organization, Employee] = Depends(deps.get_current_user),
    current_org: Organization = Depends(deps.get_current_org)
):
    org_id = _get_org_id(current_user)
    
    # Check if employee has READ permission
    has_read = True
    if not isinstance(current_user, Organization):
        has_read = deps.has_permission(db, current_user, PerformancePermissions.READ)
        
    query = db.query(OrganizationGoal).filter(OrganizationGoal.organization_id == org_id)
    
    # Filter public goals if employee doesn't have read permission
    if not has_read:
        query = query.filter(OrganizationGoal.is_public == True)

    if search:
        query = query.filter(
            or_(
                OrganizationGoal.title.ilike(f"%{search}%"),
                OrganizationGoal.description.ilike(f"%{search}%")
            )
        )
        
    if fiscal_year:
        query = query.filter(OrganizationGoal.fiscal_year == fiscal_year)
    if status_filter:
        query = query.filter(OrganizationGoal.status == status_filter)
    if framework_type:
        query = query.join(GoalFramework).filter(GoalFramework.framework_type == framework_type)
    if framework_id:
        try:
            f_uuid = uuid.UUID(str(framework_id))
            f_obj = db.query(GoalFramework).filter(GoalFramework.uuid == f_uuid, GoalFramework.organization_id == org_id).first()
        except ValueError:
            try:
                f_id = int(framework_id)
                f_obj = db.query(GoalFramework).filter(GoalFramework.id == f_id, GoalFramework.organization_id == org_id).first()
            except ValueError:
                f_obj = db.query(GoalFramework).filter(GoalFramework.name == str(framework_id), GoalFramework.organization_id == org_id).first()
        if f_obj:
            query = query.filter(OrganizationGoal.framework_id == f_obj.id)
        else:
            query = query.filter(OrganizationGoal.id == -1)
    if owner_id:
        # Resolve owner
        try:
            o_uuid = uuid.UUID(str(owner_id))
            owner_emp = db.query(Employee).filter(Employee.uuid == o_uuid, Employee.organization_id == org_id).first()
        except ValueError:
            try:
                o_id = int(owner_id)
                owner_emp = db.query(Employee).filter(Employee.id == o_id, Employee.organization_id == org_id).first()
            except ValueError:
                owner_emp = db.query(Employee).filter(Employee.email == str(owner_id), Employee.organization_id == org_id).first()
        if owner_emp:
            query = query.filter(OrganizationGoal.owner_id == owner_emp.id)
            
    total_records = query.count()
    items = query.order_by(OrganizationGoal.created_at.desc()).offset((page - 1) * limit).limit(limit).all()
    
    return OrgGoalListResponse(
        success=True,
        message="Organization goals retrieved successfully",
        data=items,
        pagination={
            "total_records": total_records,
            "current_page": page,
            "total_pages": (total_records + limit - 1) // limit if total_records > 0 else 0,
            "page_size": limit
        }
    )

@router.post("/", response_model=OrgGoalResponse, status_code=status.HTTP_201_CREATED)
def create_org_goal(
    payload: OrgGoalCreate,
    db: Session = Depends(deps.get_db),
    current_user: Union[Organization, Employee] = Depends(deps.get_current_user),
    current_org: Organization = Depends(deps.get_current_org)
):
    _require_permission(db, current_user, PerformancePermissions.CREATE, "create organizational goal")
    org_id = _get_org_id(current_user)
    
    framework_id, owner_id = _resolve_ids(db, org_id, payload)
    
    # Calculate progress percentage
    progress = _calculate_progress(payload.current_value, payload.target_value)
    
    # Create the model
    db_item = OrganizationGoal(
        organization_id=org_id,
        framework_id=framework_id,
        owner_id=owner_id,
        title=payload.title,
        description=payload.description,
        goal_type=GoalFrameworkType.OKR, # Default/placeholder framework mapped
        start_date=payload.start_date,
        end_date=payload.end_date,
        fiscal_year=payload.fiscal_year,
        measurement_type=payload.measurement_type,
        target_value=payload.target_value,
        current_value=payload.current_value,
        unit=payload.unit,
        status=payload.status or GoalStatus.DRAFT,
        weight=payload.weight if payload.weight is not None else Decimal("100.00"),
        progress_percentage=progress,
        is_public=payload.is_public if payload.is_public is not None else True,
        tags=payload.tags or [],
        attachments=payload.attachments or [],
        created_by=current_user.id if not isinstance(current_user, Organization) else None
    )
    
    db.add(db_item)
    db.commit()
    db.refresh(db_item)
    
    return {
        "success": True,
        "message": "Organization goal created successfully",
        "data": db_item
    }

@router.get("/summary", response_model=OrgGoalSummaryResponse)
def get_org_goals_summary(
    fiscal_year: Optional[str] = None,
    framework_type: Optional[GoalFrameworkType] = None,
    framework_id: Optional[str] = None,
    db: Session = Depends(deps.get_db),
    current_user: Union[Organization, Employee] = Depends(deps.get_current_user),
    current_org: Organization = Depends(deps.get_current_org)
):
    org_id = _get_org_id(current_user)
    
    # Check access (HR Admin or Manager or Public-only)
    has_read = True
    is_mgr = False
    if not isinstance(current_user, Organization):
        has_read = deps.has_permission(db, current_user, PerformancePermissions.READ)
        is_mgr = _is_manager(db, current_user.id)
        
    query = db.query(OrganizationGoal).filter(OrganizationGoal.organization_id == org_id)
    
    # Filter public goals if employee doesn't have read/manager permission
    if not has_read and not is_mgr:
        query = query.filter(OrganizationGoal.is_public == True)
        
    if fiscal_year:
        query = query.filter(OrganizationGoal.fiscal_year == fiscal_year)
    if framework_type:
        query = query.join(GoalFramework).filter(GoalFramework.framework_type == framework_type)
    if framework_id:
        try:
            f_uuid = uuid.UUID(str(framework_id))
            f_obj = db.query(GoalFramework).filter(GoalFramework.uuid == f_uuid, GoalFramework.organization_id == org_id).first()
        except ValueError:
            try:
                f_id = int(framework_id)
                f_obj = db.query(GoalFramework).filter(GoalFramework.id == f_id, GoalFramework.organization_id == org_id).first()
            except ValueError:
                f_obj = db.query(GoalFramework).filter(GoalFramework.name == str(framework_id), GoalFramework.organization_id == org_id).first()
        if f_obj:
            query = query.filter(OrganizationGoal.framework_id == f_obj.id)
        else:
            query = query.filter(OrganizationGoal.id == -1)
        
    goals = query.all()
    total = len(goals)
    
    on_track = sum(1 for g in goals if g.status == GoalStatus.ON_TRACK)
    at_risk = sum(1 for g in goals if g.status == GoalStatus.AT_RISK)
    behind = sum(1 for g in goals if g.status == GoalStatus.BEHIND)
    completed = sum(1 for g in goals if g.status == GoalStatus.COMPLETED)
    
    # Calculate average progress
    avg_progress = 0.0
    if total > 0:
        avg_progress = float(sum(g.progress_percentage or Decimal("0.00") for g in goals) / total)
    
    def _pct(val: int) -> float:
        if total == 0:
            return 0.0
        return round((val / total) * 100.0, 2)
        
    summary_data = OrgGoalSummarySchema(
        total=total,
        on_track=on_track,
        on_track_percentage=_pct(on_track),
        at_risk=at_risk,
        at_risk_percentage=_pct(at_risk),
        behind=behind,
        behind_percentage=_pct(behind),
        completed=completed,
        completed_percentage=_pct(completed),
        average_progress=avg_progress
    )
    
    return {
        "success": True,
        "message": "Aggregated goal summary retrieved successfully",
        "data": summary_data
    }

@router.get("/my-goals", response_model=OrgGoalListResponse)
def get_my_assigned_goals(
    page: int = Query(1, ge=1),
    limit: int = Query(10, ge=1, le=100),
    status: Optional[GoalStatus] = None,
    fiscal_year: Optional[str] = None,
    search: Optional[str] = None,
    db: Session = Depends(deps.get_db),
    current_user: Union[Organization, Employee] = Depends(deps.get_current_user),
    current_org: Organization = Depends(deps.get_current_org)
):
    """Returns only goals where the logged-in employee is the owner. No RBAC check needed."""
    org_id = _get_org_id(current_user)

    # Organization accounts see all public goals; employees see only their own
    if isinstance(current_user, Organization):
        query = db.query(OrganizationGoal).filter(
            OrganizationGoal.organization_id == org_id,
            OrganizationGoal.is_public == True
        )
    else:
        query = db.query(OrganizationGoal).filter(
            OrganizationGoal.organization_id == org_id,
            OrganizationGoal.owner_id == current_user.id
        )

    if status:
        query = query.filter(OrganizationGoal.status == status)
    if fiscal_year:
        query = query.filter(OrganizationGoal.fiscal_year == fiscal_year)
    if search:
        query = query.filter(OrganizationGoal.title.ilike(f"%{search}%"))

    total_records = query.count()
    items = query.order_by(OrganizationGoal.created_at.desc()).offset((page - 1) * limit).limit(limit).all()

    return OrgGoalListResponse(
        success=True,
        message="My assigned goals retrieved successfully",
        data=items,
        pagination={
            "total_records": total_records,
            "current_page": page,
            "total_pages": (total_records + limit - 1) // limit if total_records > 0 else 0,
            "page_size": limit
        }
    )

@router.get("/{goal_uuid}", response_model=OrgGoalResponse)
def get_org_goal(
    goal_uuid: uuid.UUID,
    db: Session = Depends(deps.get_db),
    current_user: Union[Organization, Employee] = Depends(deps.get_current_user),
    current_org: Organization = Depends(deps.get_current_org)
):
    org_id = _get_org_id(current_user)
    db_item = db.query(OrganizationGoal).filter(OrganizationGoal.uuid == goal_uuid, OrganizationGoal.organization_id == org_id).first()
    if not db_item:
        raise HTTPException(status_code=404, detail="Organization goal not found")

    # Organization: unrestricted access
    # Employee with READ permission: access any goal
    # Employee without permission: only own goal (owner or creator)
    if not isinstance(current_user, Organization):
        has_read = deps.has_permission(db, current_user, PerformancePermissions.READ)
        is_own = (db_item.owner_id == current_user.id) or (db_item.created_by == current_user.id)
        if not has_read and not is_own:
            raise HTTPException(status_code=403, detail="You can only access your own goals.")

    return {
        "success": True,
        "message": "Organization goal retrieved successfully",
        "data": db_item
    }

@router.put("/{goal_uuid}", response_model=OrgGoalResponse)
def update_org_goal(
    goal_uuid: uuid.UUID,
    payload: OrgGoalUpdate,
    db: Session = Depends(deps.get_db),
    current_user: Union[Organization, Employee] = Depends(deps.get_current_user),
    current_org: Organization = Depends(deps.get_current_org)
):
    org_id = _get_org_id(current_user)
    db_item = db.query(OrganizationGoal).filter(OrganizationGoal.uuid == goal_uuid, OrganizationGoal.organization_id == org_id).first()
    if not db_item:
        raise HTTPException(status_code=404, detail="Organization goal not found")
        
    if db_item.status in [GoalStatus.COMPLETED, GoalStatus.CANCELLED]:
        raise HTTPException(status_code=400, detail=f"Cannot update goal because its status is {db_item.status}")
        
    # Check access (HR Admin or Owner)
    if not isinstance(current_user, Organization):
        has_update = deps.has_permission(db, current_user, PerformancePermissions.UPDATE)
        is_owner = (db_item.owner_id == current_user.id)
        if not has_update and not is_owner:
            raise HTTPException(status_code=403, detail="You do not have permission to update this goal")
            
    # Resolve optional FKs
    framework_id, owner_id = _resolve_ids(db, org_id, payload)
    
    # Update fields
    update_data = payload.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        if field in ("framework_id", "owner_id"):
            continue
        setattr(db_item, field, value)
        
    if framework_id is not None:
        db_item.framework_id = framework_id
    if owner_id is not None:
        db_item.owner_id = owner_id
        
    # Recalculate progress if values changed
    db_item.progress_percentage = _calculate_progress(db_item.current_value, db_item.target_value)
    
    db.commit()
    db.refresh(db_item)
    
    return {
        "success": True,
        "message": "Organization goal updated successfully",
        "data": db_item
    }

@router.patch("/{goal_uuid}/status", response_model=OrgGoalResponse)
def update_org_goal_status(
    goal_uuid: uuid.UUID,
    payload: OrgGoalStatusUpdate,
    db: Session = Depends(deps.get_db),
    current_user: Union[Organization, Employee] = Depends(deps.get_current_user),
    current_org: Organization = Depends(deps.get_current_org)
):
    org_id = _get_org_id(current_user)
    db_item = db.query(OrganizationGoal).filter(OrganizationGoal.uuid == goal_uuid, OrganizationGoal.organization_id == org_id).first()
    if not db_item:
        raise HTTPException(status_code=404, detail="Organization goal not found")
        
    if db_item.status in [GoalStatus.COMPLETED, GoalStatus.CANCELLED]:
        raise HTTPException(status_code=400, detail=f"Cannot change status because the goal is already {db_item.status}")
        
    # Check access (HR Admin or Owner)
    if not isinstance(current_user, Organization):
        has_update = deps.has_permission(db, current_user, PerformancePermissions.UPDATE)
        is_owner = (db_item.owner_id == current_user.id)
        if not has_update and not is_owner:
            raise HTTPException(status_code=403, detail="You do not have permission to update this goal status")
            
    db_item.status = payload.status
    if payload.notes is not None:
        db_item.status_notes = payload.notes
    
    db.commit()
    db.refresh(db_item)
    
    return {
        "success": True,
        "message": "Goal status updated successfully",
        "data": db_item
    }

@router.delete("/{goal_uuid}")
def delete_org_goal(
    goal_uuid: uuid.UUID,
    db: Session = Depends(deps.get_db),
    current_user: Union[Organization, Employee] = Depends(deps.get_current_user),
    current_org: Organization = Depends(deps.get_current_org)
):
    _require_permission(db, current_user, PerformancePermissions.DELETE, "delete organizational goal")
    org_id = _get_org_id(current_user)
    
    db_item = db.query(OrganizationGoal).filter(OrganizationGoal.uuid == goal_uuid, OrganizationGoal.organization_id == org_id).first()
    if not db_item:
        raise HTTPException(status_code=404, detail="Organization goal not found")
        
    db.delete(db_item)
    db.commit()
    
    return {
        "success": True,
        "message": "Organization goal deleted successfully"
    }

@router.get("/{goal_uuid}/cascade", response_model=GoalCascadeResponse)
def get_org_goal_cascade(
    goal_uuid: uuid.UUID,
    db: Session = Depends(deps.get_db),
    current_user: Union[Organization, Employee] = Depends(deps.get_current_user),
    current_org: Organization = Depends(deps.get_current_org)
):
    org_id = _get_org_id(current_user)

    # Fetch goal first so we can check ownership
    org_goal = db.query(OrganizationGoal).filter(OrganizationGoal.uuid == goal_uuid, OrganizationGoal.organization_id == org_id).first()
    if not org_goal:
        raise HTTPException(status_code=404, detail="Organization goal not found")

    # Organization: unrestricted
    # Employee with READ permission: access any
    # Employee without permission: only own goal
    if not isinstance(current_user, Organization):
        has_read = deps.has_permission(db, current_user, PerformancePermissions.READ)
        is_own = (org_goal.owner_id == current_user.id) or (org_goal.created_by == current_user.id)
        if not has_read and not is_own:
            raise HTTPException(status_code=403, detail="You can only view cascade for your own goals.")
        
    # Build tree
    org_node = GoalCascadeItem(
        uuid=org_goal.uuid,
        title=org_goal.title,
        goal_type="ORGANIZATION",
        status=org_goal.status,
        progress_percentage=org_goal.progress_percentage or Decimal("0.00"),
        owner_name=f"{org_goal.owner.first_name} {org_goal.owner.last_name}" if org_goal.owner else "N/A",
        children=[]
    )
    
    # Fetch department goals aligned to this org goal
    dept_goals = db.query(DepartmentGoal).filter(
        DepartmentGoal.parent_org_goal_id == org_goal.id,
        DepartmentGoal.organization_id == org_id
    ).all()
    
    dept_nodes_map = {}
    for dg in dept_goals:
        dg_node = GoalCascadeItem(
            uuid=dg.uuid,
            title=dg.title,
            goal_type="DEPARTMENT",
            status=dg.status,
            progress_percentage=dg.progress_percentage or Decimal("0.00"),
            owner_name=f"{dg.owner.first_name} {dg.owner.last_name}" if dg.owner else "N/A",
            children=[]
        )
        dept_nodes_map[dg.id] = dg_node
        org_node.children.append(dg_node)
        
    # Fetch individual goals
    emp_goals = db.query(EmployeeGoal).filter(
        EmployeeGoal.parent_org_goal_id == org_goal.id,
        EmployeeGoal.organization_id == org_id
    ).all()
    
    for eg in emp_goals:
        eg_node = GoalCascadeItem(
            uuid=eg.uuid,
            title=eg.title,
            goal_type="INDIVIDUAL",
            status=eg.status,
            progress_percentage=eg.progress_percentage or Decimal("0.00"),
            owner_name=f"{eg.employee.first_name} {eg.employee.last_name}" if eg.employee else "N/A",
            children=[]
        )
        if eg.parent_dept_goal_id and eg.parent_dept_goal_id in dept_nodes_map:
            dept_nodes_map[eg.parent_dept_goal_id].children.append(eg_node)
        else:
            org_node.children.append(eg_node)
            
    return {
        "success": True,
        "message": "Cascade tree retrieved successfully",
        "data": org_node
    }


