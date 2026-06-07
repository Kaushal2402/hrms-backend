import uuid
from typing import List, Optional, Union
from decimal import Decimal
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from sqlalchemy import or_, and_, func, case

from app.api import deps
from app.models.organization import Organization
from app.models.employee import Employee, Department
from app.models.performance import OrganizationGoal, GoalFramework, DepartmentGoal, GoalStatus, GoalFrameworkType
from app.schemas.performance_dept_goals import (
    DeptGoalCreate, DeptGoalUpdate, DeptGoalStatusUpdate, DeptGoalSchema,
    DeptGoalResponse, DeptGoalListResponse, DeptGoalLookupResponse
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
    framework_val = getattr(payload, "framework_uuid", None)
    framework_id = None
    if framework_val is not None:
        f_obj = db.query(GoalFramework).filter(GoalFramework.uuid == framework_val, GoalFramework.organization_id == org_id).first()
        if not f_obj:
            raise HTTPException(status_code=404, detail=f"Goal framework '{framework_val}' not found")
        framework_id = f_obj.id

    # Resolve owner_id
    owner_val = getattr(payload, "owner_uuid", None)
    owner_id = None
    if owner_val is not None:
        o_obj = db.query(Employee).filter(Employee.uuid == owner_val, Employee.organization_id == org_id).first()
        if not o_obj:
            raise HTTPException(status_code=404, detail=f"Owner employee '{owner_val}' not found")
        owner_id = o_obj.id

    # Resolve department_id
    dept_val = getattr(payload, "department_uuid", None)
    department_id = None
    if dept_val is not None:
        d_obj = db.query(Department).filter(Department.uuid == dept_val, Department.organization_id == org_id).first()
        if not d_obj:
            raise HTTPException(status_code=404, detail=f"Department '{dept_val}' not found")
        department_id = d_obj.id

    # Resolve parent_org_goal_id
    parent_val = getattr(payload, "parent_org_goal_uuid", None)
    parent_org_goal_id = None
    if parent_val is not None:
        p_obj = db.query(OrganizationGoal).filter(OrganizationGoal.uuid == parent_val, OrganizationGoal.organization_id == org_id).first()
        if not p_obj:
            raise HTTPException(status_code=404, detail=f"Parent organization goal '{parent_val}' not found")
        parent_org_goal_id = p_obj.id

    return framework_id, owner_id, department_id, parent_org_goal_id

@router.get("/", response_model=DeptGoalListResponse)
def list_department_goals(
    department_uuid: Optional[uuid.UUID] = None,
    fiscal_year: Optional[str] = None,
    status_filter: Optional[GoalStatus] = Query(None, alias="status"),
    framework_uuid: Optional[uuid.UUID] = None,
    parent_org_goal_uuid: Optional[uuid.UUID] = None,
    search: Optional[str] = Query(None),
    sort_by: Optional[str] = Query(None),
    sort_order: Optional[str] = Query('asc'),
    page: int = Query(1, ge=1),
    limit: int = Query(10, ge=1, le=100),
    db: Session = Depends(deps.get_db),
    current_user: Union[Organization, Employee] = Depends(deps.get_current_user),
    current_org: Organization = Depends(deps.get_current_org)
):
    org_id = _get_org_id(current_user)
    
    query = db.query(DepartmentGoal).filter(
        DepartmentGoal.organization_id == org_id,
        DepartmentGoal.is_deleted == False
    )

    _require_permission(db, current_user, PerformancePermissions.READ, "list department goals")

    # Filters
    if department_uuid:
        d_obj = db.query(Department).filter(Department.uuid == department_uuid, Department.organization_id == org_id).first()
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
    if framework_uuid:
        f_obj = db.query(GoalFramework).filter(GoalFramework.uuid == framework_uuid, GoalFramework.organization_id == org_id).first()
        if f_obj:
            query = query.filter(DepartmentGoal.framework_id == f_obj.id)
        else:
            query = query.filter(DepartmentGoal.id == -1)

    if parent_org_goal_uuid:
        p_obj = db.query(OrganizationGoal).filter(OrganizationGoal.uuid == parent_org_goal_uuid, OrganizationGoal.organization_id == org_id).first()
        if p_obj:
            query = query.filter(DepartmentGoal.parent_org_goal_id == p_obj.id)
        else:
            query = query.filter(DepartmentGoal.id == -1)
            
    total_records = query.count()
    
    if sort_by:
        sort_column = None
        if sort_by == 'title':
            sort_column = DepartmentGoal.title
        elif sort_by == 'progress_percentage':
            sort_column = DepartmentGoal.progress_percentage
        elif sort_by == 'status':
            sort_column = DepartmentGoal.status
            
        if sort_column is not None:
            if sort_order == 'desc':
                query = query.order_by(sort_column.desc())
            else:
                query = query.order_by(sort_column.asc())
        else:
            query = query.order_by(DepartmentGoal.created_at.desc())
    else:
        query = query.order_by(DepartmentGoal.created_at.desc())
        
    items = query.offset((page - 1) * limit).limit(limit).all()
    
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

@router.get("/lookup", response_model=DeptGoalLookupResponse)
def lookup_department_goals(
    department_uuid: Optional[uuid.UUID] = None,
    fiscal_year: Optional[str] = None,
    status_filter: Optional[GoalStatus] = Query(None, alias="status"),
    framework_uuid: Optional[uuid.UUID] = None,
    parent_org_goal_uuid: Optional[uuid.UUID] = None,
    search: Optional[str] = Query(None),
    sort_by: Optional[str] = Query(None),
    sort_order: Optional[str] = Query('asc'),
    page: int = Query(1, ge=1),
    limit: int = Query(10, ge=1, le=100),
    db: Session = Depends(deps.get_db),
    current_user: Union[Organization, Employee] = Depends(deps.get_current_user),
    current_org: Organization = Depends(deps.get_current_org)
):
    # No permission check here as per user request
    org_id = _get_org_id(current_user)
    
    query = db.query(DepartmentGoal).filter(
        DepartmentGoal.organization_id == org_id,
        DepartmentGoal.is_deleted == False
    )

    # Filters
    if department_uuid:
        d_obj = db.query(Department).filter(Department.uuid == department_uuid, Department.organization_id == org_id).first()
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
    if framework_uuid:
        f_obj = db.query(GoalFramework).filter(GoalFramework.uuid == framework_uuid, GoalFramework.organization_id == org_id).first()
        if f_obj:
            query = query.filter(DepartmentGoal.framework_id == f_obj.id)
        else:
            query = query.filter(DepartmentGoal.id == -1)

    if parent_org_goal_uuid:
        p_obj = db.query(OrganizationGoal).filter(OrganizationGoal.uuid == parent_org_goal_uuid, OrganizationGoal.organization_id == org_id).first()
        if p_obj:
            query = query.filter(DepartmentGoal.parent_org_goal_id == p_obj.id)
        else:
            query = query.filter(DepartmentGoal.id == -1)
            
    total_records = query.count()
    
    if sort_by:
        sort_column = None
        if sort_by == 'title':
            sort_column = DepartmentGoal.title
        elif sort_by == 'progress_percentage':
            sort_column = DepartmentGoal.progress_percentage
        elif sort_by == 'status':
            sort_column = DepartmentGoal.status
            
        if sort_column is not None:
            if sort_order == 'desc':
                query = query.order_by(sort_column.desc())
            else:
                query = query.order_by(sort_column.asc())
        else:
            query = query.order_by(DepartmentGoal.created_at.desc())
    else:
        query = query.order_by(DepartmentGoal.created_at.desc())
        
    items = query.offset((page - 1) * limit).limit(limit).all()
    
    # Map the Department details manually since they might not be fully loaded
    lookup_items = []
    for item in items:
        lookup_items.append({
            "uuid": item.uuid,
            "title": item.title,
            "status": item.status,
            "department_name": item.department.department_name if item.department else None,
            "progress_percentage": item.progress_percentage
        })
    
    return DeptGoalLookupResponse(
        success=True,
        message="Department goals lookup retrieved successfully",
        data=lookup_items,
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
        created_by=current_user.id if not isinstance(current_user, Organization) else owner_id
    )
    
    db.add(db_item)
    db.commit()
    db.refresh(db_item)
    
    return {
        "success": True,
        "message": "Department goal created successfully",
        "data": db_item
    }

@router.put("/{goal_uuid}", response_model=DeptGoalResponse)
def update_department_goal(
    goal_uuid: uuid.UUID,
    payload: DeptGoalUpdate,
    db: Session = Depends(deps.get_db),
    current_user: Union[Organization, Employee] = Depends(deps.get_current_user),
    current_org: Organization = Depends(deps.get_current_org)
):
    _require_permission(db, current_user, PerformancePermissions.UPDATE, "update department goal")
    org_id = _get_org_id(current_user)
    
    db_item = db.query(DepartmentGoal).filter(
        DepartmentGoal.uuid == goal_uuid,
        DepartmentGoal.organization_id == org_id
    ).first()
    
    if not db_item:
        raise HTTPException(status_code=404, detail="Department goal not found")
        
    framework_id, owner_id, department_id, parent_org_goal_id = _resolve_ids(db, org_id, payload)
    
    update_data = payload.dict(exclude_unset=True)
    
    if framework_id is not None:
        db_item.framework_id = framework_id
    if owner_id is not None:
        db_item.owner_id = owner_id
    if department_id is not None:
        db_item.department_id = department_id
    if "parent_org_goal_uuid" in update_data:
        db_item.parent_org_goal_id = parent_org_goal_id
        
    for field in ["title", "description", "start_date", "end_date", "fiscal_year", 
                  "measurement_type", "target_value", "current_value", "unit", 
                  "status", "weight", "tags"]:
        if field in update_data:
            setattr(db_item, field, update_data[field])
            
    if "current_value" in update_data or "target_value" in update_data:
        db_item.progress_percentage = _calculate_progress(db_item.current_value, db_item.target_value)
        
    db.commit()
    db.refresh(db_item)
    
    return {
        "success": True,
        "message": "Department goal updated successfully",
        "data": db_item
    }

@router.get("/summary")
def get_department_goals_summary(
    fiscal_year: Optional[str] = None,
    department_uuid: Optional[uuid.UUID] = None,
    db: Session = Depends(deps.get_db),
    current_user: Union[Organization, Employee] = Depends(deps.get_current_user)
):
    org_id = _get_org_id(current_user)
    
    query = db.query(DepartmentGoal).join(Department, DepartmentGoal.department_id == Department.id).filter(
        DepartmentGoal.organization_id == org_id,
        DepartmentGoal.is_deleted == False
    )

    _require_permission(db, current_user, PerformancePermissions.READ, "view department goals summary")

    if fiscal_year:
        query = query.filter(DepartmentGoal.fiscal_year == fiscal_year)

    if department_uuid:
        d_obj = db.query(Department).filter(Department.uuid == department_uuid, Department.organization_id == org_id).first()
        if d_obj:
            query = query.filter(DepartmentGoal.department_id == d_obj.id)
        else:
            query = query.filter(DepartmentGoal.id == -1)

    goals = query.all()

    # Group by department
    summary_by_dept = {}
    for g in goals:
        dept_id = g.department_id
        if dept_id not in summary_by_dept:
            summary_by_dept[dept_id] = {
                "department_uuid": str(g.department.uuid) if g.department else None,
                "department_name": g.department.department_name if g.department else "Unknown",
                "total_goals": 0,
                "status_counts": {
                    "COMPLETED": 0, "ON_TRACK": 0, "AT_RISK": 0, "BEHIND": 0, "DRAFT": 0, "ACTIVE": 0
                },
                "total_progress": 0
            }
        
        entry = summary_by_dept[dept_id]
        entry["total_goals"] += 1
        status_name = g.status.name if g.status else "DRAFT"
        if status_name in entry["status_counts"]:
            entry["status_counts"][status_name] += 1
        
        entry["total_progress"] += float(g.progress_percentage) if g.progress_percentage else 0

    results = []
    for dept_id, stats in summary_by_dept.items():
        avg = stats["total_progress"] / stats["total_goals"] if stats["total_goals"] > 0 else 0
        results.append({
            "department_uuid": stats["department_uuid"],
            "department_name": stats["department_name"],
            "total_goals": stats["total_goals"],
            "average_progress": round(avg, 2),
            "status_counts": stats["status_counts"]
        })

    # Sort alphabetically by department name
    results.sort(key=lambda x: x["department_name"])

    return {
        "success": True,
        "message": "Summary retrieved successfully",
        "data": results
    }

@router.get("/{goal_uuid}", response_model=DeptGoalResponse)
def get_department_goal(
    goal_uuid: uuid.UUID,
    db: Session = Depends(deps.get_db),
    current_user: Union[Organization, Employee] = Depends(deps.get_current_user),
    current_org: Organization = Depends(deps.get_current_org)
):
    org_id = _get_org_id(current_user)
    
    query = db.query(DepartmentGoal).filter(
        DepartmentGoal.uuid == goal_uuid,
        DepartmentGoal.organization_id == org_id,
        DepartmentGoal.is_deleted == False
    )
    
    _require_permission(db, current_user, PerformancePermissions.READ, "view department goal")
            
    db_item = query.first()
    
    if not db_item:
        raise HTTPException(status_code=404, detail="Department goal not found")
        
    return {
        "success": True,
        "message": "Department goal retrieved successfully",
        "data": db_item
    }

@router.delete("/{goal_uuid}")
def delete_department_goal(
    goal_uuid: uuid.UUID,
    db: Session = Depends(deps.get_db),
    current_user: Union[Organization, Employee] = Depends(deps.get_current_user),
    current_org: Organization = Depends(deps.get_current_org)
):
    _require_permission(db, current_user, PerformancePermissions.DELETE, "delete department goal")
    org_id = _get_org_id(current_user)
    
    db_item = db.query(DepartmentGoal).filter(
        DepartmentGoal.uuid == goal_uuid,
        DepartmentGoal.organization_id == org_id,
        DepartmentGoal.is_deleted == False
    ).first()
    
    if not db_item:
        raise HTTPException(status_code=404, detail="Department goal not found")
        
    db_item.is_deleted = True
    db_item.deleted_at = datetime.utcnow()
    db.commit()
    
    return {
        "success": True,
        "message": "Department goal deleted successfully"
    }

@router.get("/{goal_uuid}/cascade")
def get_department_goal_cascade(
    goal_uuid: uuid.UUID,
    db: Session = Depends(deps.get_db),
    current_user: Union[Organization, Employee] = Depends(deps.get_current_user)
):
    _require_permission(db, current_user, PerformancePermissions.READ, "view department goal cascade")
    org_id = _get_org_id(current_user)
    
    dept_goal = db.query(DepartmentGoal).filter(
        DepartmentGoal.uuid == goal_uuid,
        DepartmentGoal.organization_id == org_id,
        DepartmentGoal.is_deleted == False
    ).first()
    
    if not dept_goal:
        raise HTTPException(status_code=404, detail="Department goal not found")
        
    from app.models.performance import EmployeeGoal
    
    emp_goals = db.query(EmployeeGoal).filter(
        EmployeeGoal.parent_dept_goal_id == dept_goal.id,
        EmployeeGoal.organization_id == org_id
    ).all()
    
    children = []
    for eg in emp_goals:
        children.append({
            "uuid": str(eg.uuid),
            "title": eg.title,
            "status": eg.status,
            "progress_percentage": float(eg.progress_percentage) if eg.progress_percentage else 0,
            "owner": {
                "first_name": eg.employee.first_name if eg.employee else None,
                "last_name": eg.employee.last_name if eg.employee else None,
                "uuid": str(eg.employee.uuid) if eg.employee else None
            }
        })
        
    return {
        "success": True,
        "message": "Cascade retrieved successfully",
        "data": {
            "uuid": str(dept_goal.uuid),
            "title": dept_goal.title,
            "status": dept_goal.status,
            "progress_percentage": float(dept_goal.progress_percentage) if dept_goal.progress_percentage else 0,
            "children": children
        }
    }
