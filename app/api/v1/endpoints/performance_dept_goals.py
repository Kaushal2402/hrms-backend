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
from app.models.department import Department
from app.models.performance import OrganizationGoal, GoalFramework, DepartmentGoal, GoalStatus, GoalFrameworkType
from app.schemas.performance_dept_goals import (
    DeptGoalCreate, DeptGoalUpdate, DeptGoalStatusUpdate, DeptGoalSchema,
    DeptGoalResponse, DeptGoalListResponse
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

def _calculate_progress(current_val: Optional[Decimal], target_val: Optional[Decimal]) -> Decimal:
    if not target_val or target_val == Decimal("0.00"):
        return Decimal("0.00")
    if current_val is None:
        current_val = Decimal("0.00")
    progress = (current_val / target_val) * Decimal("100.00")
    return min(max(progress, Decimal("0.00")), Decimal("100.00"))

def _resolve_ids(db: Session, org_id: int, payload) -> tuple[int, int, int, Optional[int]]:
    # Resolve framework_id
    framework_val = getattr(payload, "framework_id", None)
    framework_id = None
    if framework_val is not None:
        if isinstance(framework_val, int):
            f_obj = db.query(GoalFramework).filter(GoalFramework.id == framework_val, GoalFramework.organization_id == org_id).first()
        else:
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

    # Resolve department_id
    dept_val = getattr(payload, "department_id", None)
    department_id = None
    if dept_val is not None:
        if isinstance(dept_val, int):
            d_obj = db.query(Department).filter(Department.id == dept_val, Department.organization_id == org_id).first()
        else:
            try:
                val_uuid = uuid.UUID(str(dept_val))
                d_obj = db.query(Department).filter(Department.uuid == val_uuid, Department.organization_id == org_id).first()
            except ValueError:
                d_obj = db.query(Department).filter(Department.name == str(dept_val), Department.organization_id == org_id).first()
        if not d_obj:
            raise HTTPException(status_code=404, detail=f"Department '{dept_val}' not found")
        department_id = d_obj.id

    # Resolve parent_org_goal_id
    parent_val = getattr(payload, "parent_org_goal_id", None)
    parent_org_goal_id = None
    if parent_val is not None:
        if isinstance(parent_val, int):
            p_obj = db.query(OrganizationGoal).filter(OrganizationGoal.id == parent_val, OrganizationGoal.organization_id == org_id).first()
        else:
            try:
                val_uuid = uuid.UUID(str(parent_val))
                p_obj = db.query(OrganizationGoal).filter(OrganizationGoal.uuid == val_uuid, OrganizationGoal.organization_id == org_id).first()
            except ValueError:
                raise HTTPException(status_code=400, detail="Invalid parent organization goal ID format")
        if not p_obj:
            raise HTTPException(status_code=404, detail=f"Parent organization goal '{parent_val}' not found")
        parent_org_goal_id = p_obj.id

    return framework_id, owner_id, department_id, parent_org_goal_id

@router.get("/", response_model=DeptGoalListResponse)
def list_department_goals(
    department_id: Optional[str] = None,
    fiscal_year: Optional[str] = None,
    status_filter: Optional[GoalStatus] = Query(None, alias="status"),
    framework_type: Optional[GoalFrameworkType] = None,
    parent_org_goal_id: Optional[str] = None,
    search: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    limit: int = Query(10, ge=1, le=100),
    db: Session = Depends(deps.get_db),
    current_user: Union[Organization, Employee] = Depends(deps.get_current_user),
    current_org: Organization = Depends(deps.get_current_org)
):
    org_id = _get_org_id(current_user)
    
    query = db.query(DepartmentGoal).filter(DepartmentGoal.organization_id == org_id)

    # RBAC logic
    if not isinstance(current_user, Organization):
        has_read = deps.has_permission(db, current_user, PerformancePermissions.READ)
        if not has_read:
            # Only see goals for their own department
            query = query.filter(DepartmentGoal.department_id == current_user.department_id)

    # Filters
    if department_id:
        try:
            d_uuid = uuid.UUID(str(department_id))
            d_obj = db.query(Department).filter(Department.uuid == d_uuid, Department.organization_id == org_id).first()
        except ValueError:
            try:
                d_id = int(department_id)
                d_obj = db.query(Department).filter(Department.id == d_id, Department.organization_id == org_id).first()
            except ValueError:
                d_obj = db.query(Department).filter(Department.name == str(department_id), Department.organization_id == org_id).first()
        if d_obj:
            query = query.filter(DepartmentGoal.department_id == d_obj.id)
        else:
            query = query.filter(DepartmentGoal.id == -1)

    if search:
        query = query.filter(
            or_(
                DepartmentGoal.title.ilike(f"%{search}%"),
                DepartmentGoal.description.ilike(f"%{search}%")
            )
        )
        
    if fiscal_year:
        query = query.filter(DepartmentGoal.fiscal_year == fiscal_year)
    if status_filter:
        query = query.filter(DepartmentGoal.status == status_filter)
    if framework_type:
        query = query.join(GoalFramework).filter(GoalFramework.framework_type == framework_type)

    if parent_org_goal_id:
        try:
            p_uuid = uuid.UUID(str(parent_org_goal_id))
            p_obj = db.query(OrganizationGoal).filter(OrganizationGoal.uuid == p_uuid, OrganizationGoal.organization_id == org_id).first()
        except ValueError:
            p_obj = None
        if p_obj:
            query = query.filter(DepartmentGoal.parent_org_goal_id == p_obj.id)
        else:
            query = query.filter(DepartmentGoal.id == -1)
            
    total_records = query.count()
    items = query.order_by(DepartmentGoal.created_at.desc()).offset((page - 1) * limit).limit(limit).all()
    
    return DeptGoalListResponse(
        success=True,
        message="Department goals retrieved successfully",
        data=items,
        pagination={
            "total_records": total_records,
            "current_page": page,
            "total_pages": (total_records + limit - 1) // limit if total_records > 0 else 0,
            "page_size": limit
        }
    )

@router.post("/", response_model=DeptGoalResponse, status_code=status.HTTP_201_CREATED)
def create_department_goal(
    payload: DeptGoalCreate,
    db: Session = Depends(deps.get_db),
    current_user: Union[Organization, Employee] = Depends(deps.get_current_user),
    current_org: Organization = Depends(deps.get_current_org)
):
    _require_permission(db, current_user, PerformancePermissions.CREATE, "create department goal")
    org_id = _get_org_id(current_user)
    
    framework_id, owner_id, department_id, parent_org_goal_id = _resolve_ids(db, org_id, payload)
    
    progress = _calculate_progress(payload.current_value, payload.target_value)
    
    db_item = DepartmentGoal(
        organization_id=org_id,
        department_id=department_id,
        framework_id=framework_id,
        owner_id=owner_id,
        parent_org_goal_id=parent_org_goal_id,
        title=payload.title,
        description=payload.description,
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
        tags=payload.tags or [],
        created_by=current_user.id if not isinstance(current_user, Organization) else None
    )
    
    db.add(db_item)
    db.commit()
    db.refresh(db_item)
    
    return {
        "success": True,
        "message": "Department goal created successfully",
        "data": db_item
    }
