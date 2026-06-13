from datetime import datetime, date
import uuid
from typing import List, Optional, Union
from decimal import Decimal
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from sqlalchemy import or_

from app.api import deps
from app.models.organization import Organization
from app.models.employee import Employee
from app.models.performance import EmployeeGoal, GoalFramework, GoalStatus, GoalFrameworkType, GoalProgress
from app.schemas import performance_emp_goals as schema
from app.schemas.performance_emp_goals import EmployeeGoalListResponse, EmployeeGoalSchema, EmployeeGoalCreate, EmployeeGoalResponse, EmployeeGoalUpdate, GoalApprovalRequest, GoalStatusUpdateRequest, MyGoalsDashboardResponse, MyGoalsGroup, GoalProgressCreate, GoalProgressUpdate, GoalProgressAcknowledge, GoalProgressResponse, GoalProgressListResponse, EmployeeGoalLookupResponse, EmployeeGoalLookupSchema

router = APIRouter()

class PerformancePermissions:
    READ = "205"
    CREATE = "206"
    UPDATE = "207"
    DELETE = "208"

def _get_org_id(current_user: Union[Organization, Employee]) -> int:
    return current_user.id if isinstance(current_user, Organization) else current_user.organization_id

def _calculate_progress(current_val: Optional[Decimal], target_val: Optional[Decimal]) -> Decimal:
    if not target_val or target_val == Decimal("0.00"):
        return Decimal("0.00")
    if current_val is None:
        current_val = Decimal("0.00")
    progress = (current_val / target_val) * Decimal("100.00")
    return min(max(progress, Decimal("0.00")), Decimal("100.00"))

def _resolve_ids(db: Session, org_id: int, payload: EmployeeGoalCreate) -> tuple:
    # Resolve employee
    emp = db.query(Employee).filter(Employee.uuid == payload.employee_uuid, Employee.organization_id == org_id).first()
    if not emp:
        raise HTTPException(status_code=404, detail="Employee not found")
        
    # Resolve framework
    fw = db.query(GoalFramework).filter(GoalFramework.uuid == payload.framework_uuid, GoalFramework.organization_id == org_id).first()
    if not fw:
        raise HTTPException(status_code=404, detail="Framework not found")
        
    # Resolve optional parent_dept_goal
    parent_dept_id = None
    if payload.parent_dept_goal_uuid:
        from app.models.performance import DepartmentGoal
        dg = db.query(DepartmentGoal).filter(DepartmentGoal.uuid == payload.parent_dept_goal_uuid, DepartmentGoal.organization_id == org_id).first()
        if not dg:
            raise HTTPException(status_code=404, detail="Parent department goal not found")
        parent_dept_id = dg.id
        
    # Resolve optional parent_org_goal
    parent_org_id = None
    if payload.parent_org_goal_uuid:
        from app.models.performance import OrganizationGoal
        og = db.query(OrganizationGoal).filter(OrganizationGoal.uuid == payload.parent_org_goal_uuid, OrganizationGoal.organization_id == org_id).first()
        if not og:
            raise HTTPException(status_code=404, detail="Parent organization goal not found")
        parent_org_id = og.id
        
    # Resolve optional appraisal_cycle
    appraisal_cycle_id = None
    if payload.appraisal_cycle_uuid:
        from app.models.performance import AppraisalCycle
        ac = db.query(AppraisalCycle).filter(AppraisalCycle.uuid == payload.appraisal_cycle_uuid, AppraisalCycle.organization_id == org_id).first()
        if not ac:
            raise HTTPException(status_code=404, detail="Appraisal cycle not found")
        appraisal_cycle_id = ac.id
        
    # Resolve optional parent_objective
    parent_objective_id = None
    if payload.parent_objective_uuid:
        po = db.query(EmployeeGoal).filter(EmployeeGoal.is_deleted == False, EmployeeGoal.uuid == payload.parent_objective_uuid, EmployeeGoal.organization_id == org_id).first()
        if not po:
            raise HTTPException(status_code=404, detail="Parent objective not found")
        parent_objective_id = po.id
        
    return emp.id, fw.id, parent_dept_id, parent_org_id, appraisal_cycle_id, parent_objective_id

@router.get("/", response_model=EmployeeGoalListResponse)
def list_employee_goals(
    employee_id: Optional[str] = None,
    manager_id: Optional[str] = None,
    appraisal_cycle_id: Optional[str] = None,
    status_filter: Optional[GoalStatus] = Query(None, alias="status"),
    framework_type: Optional[GoalFrameworkType] = None,
    fiscal_year: Optional[str] = None, # Employee goals don't have fiscal_year in model but might be queried by it? Wait, let's see. Wait, I'll filter by appraisal_cycle or date if needed. Wait, model has no fiscal_year, but it has start_date/end_date. I'll ignore fiscal_year or join with department goals if needed. Actually, let's just ignore fiscal_year if it's not in the model, or check if it exists.
    is_stretch_goal: Optional[bool] = None,
    search: Optional[str] = Query(None),
    sort_by: Optional[str] = Query(None),
    sort_order: Optional[str] = Query('asc'),
    page: int = Query(1, ge=1),
    limit: int = Query(10, ge=1, le=100),
    db: Session = Depends(deps.get_db),
    current_user: Union[Organization, Employee] = Depends(deps.get_current_user)
):
    org_id = _get_org_id(current_user)
    
    query = db.query(EmployeeGoal).filter(EmployeeGoal.is_deleted == False, EmployeeGoal.organization_id == org_id)

    # RBAC logic
    # 1. Organization can access without any permissions
    # 2. Employee Login if have permissions they can access all employee goals
    # 3. Employee Login if don't have permissions then they can only access own assigned goals
    if not isinstance(current_user, Organization):
        has_read = deps.has_permission(db, current_user, PerformancePermissions.READ)
        if not has_read:
            query = query.filter(EmployeeGoal.employee_id == current_user.id)

    # Filters
    if employee_id:
        try:
            emp_uuid = uuid.UUID(str(employee_id))
            emp = db.query(Employee).filter(Employee.uuid == emp_uuid, Employee.organization_id == org_id).first()
        except ValueError:
            try:
                e_id = int(employee_id)
                emp = db.query(Employee).filter(Employee.id == e_id, Employee.organization_id == org_id).first()
            except ValueError:
                emp = None
        if emp:
            query = query.filter(EmployeeGoal.employee_id == emp.id)
        else:
            query = query.filter(EmployeeGoal.id == -1)

    if manager_id:
        try:
            mgr_uuid = uuid.UUID(str(manager_id))
            mgr = db.query(Employee).filter(Employee.uuid == mgr_uuid, Employee.organization_id == org_id).first()
        except ValueError:
            try:
                m_id = int(manager_id)
                mgr = db.query(Employee).filter(Employee.id == m_id, Employee.organization_id == org_id).first()
            except ValueError:
                mgr = None
        if mgr:
            query = query.filter(EmployeeGoal.manager_id == mgr.id)
        else:
            query = query.filter(EmployeeGoal.id == -1)

    if appraisal_cycle_id:
        try:
            ac_uuid = uuid.UUID(str(appraisal_cycle_id))
            from app.models.performance import AppraisalCycle
            ac = db.query(AppraisalCycle).filter(AppraisalCycle.uuid == ac_uuid, AppraisalCycle.organization_id == org_id).first()
        except ValueError:
            try:
                ac_id = int(appraisal_cycle_id)
                from app.models.performance import AppraisalCycle
                ac = db.query(AppraisalCycle).filter(AppraisalCycle.id == ac_id, AppraisalCycle.organization_id == org_id).first()
            except ValueError:
                ac = None
        if ac:
            query = query.filter(EmployeeGoal.appraisal_cycle_id == ac.id)
        else:
            query = query.filter(EmployeeGoal.id == -1)

    if status_filter:
        query = query.filter(EmployeeGoal.status == status_filter)

    if is_stretch_goal is not None:
        query = query.filter(EmployeeGoal.is_stretch_goal == is_stretch_goal)

    if framework_type:
        query = query.join(GoalFramework).filter(GoalFramework.framework_type == framework_type)

    if search:
        query = query.filter(
            or_(
                EmployeeGoal.title.ilike(f"%{search}%"),
                EmployeeGoal.description.ilike(f"%{search}%")
            )
        )

    total_records = query.count()
    
    if sort_by:
        sort_column = None
        if sort_by == 'title':
            sort_column = EmployeeGoal.title
        elif sort_by == 'progress_percentage':
            sort_column = EmployeeGoal.progress_percentage
        elif sort_by == 'status':
            sort_column = EmployeeGoal.status
        elif sort_by == 'start_date':
            sort_column = EmployeeGoal.start_date
        elif sort_by == 'end_date':
            sort_column = EmployeeGoal.end_date
            
        if sort_column is not None:
            if sort_order == 'desc':
                query = query.order_by(sort_column.desc())
            else:
                query = query.order_by(sort_column.asc())
        else:
            query = query.order_by(EmployeeGoal.id.desc())
    else:
        query = query.order_by(EmployeeGoal.id.desc())
        
    goals = query.offset((page - 1) * limit).limit(limit).all()
    
    # Map to schema output
    items = []
    for g in goals:
        schema_data = EmployeeGoalSchema.model_validate(g)
        if g.employee:
            schema_data.employee_name = f"{g.employee.first_name} {g.employee.last_name}".strip()
        if g.manager:
            schema_data.manager_name = f"{g.manager.first_name} {g.manager.last_name}".strip()
        if g.framework:
            schema_data.framework_name = g.framework.name
        items.append(schema_data)
    
    return EmployeeGoalListResponse(
        success=True,
        message="Employee goals retrieved successfully",
        data=items,
        pagination={
            "total_records": total_records,
            "current_page": page,
            "total_pages": (total_records + limit - 1) // limit if total_records > 0 else 0,
            "page_size": limit
        }
    )

@router.post("/", response_model=EmployeeGoalResponse, status_code=status.HTTP_201_CREATED)
def create_employee_goal(
    payload: EmployeeGoalCreate,
    db: Session = Depends(deps.get_db),
    current_user: Union[Organization, Employee] = Depends(deps.get_current_user)
):
    org_id = _get_org_id(current_user)
    
    # RBAC checks
    if not isinstance(current_user, Organization):
        has_create = deps.has_permission(db, current_user, PerformancePermissions.CREATE)
        if not has_create:
            # Employee without CREATE permission can only add goals for themselves
            if payload.employee_uuid != current_user.uuid:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN, 
                    detail="You do not have permission to create goals for other employees."
                )
                
    emp_id, fw_id, dept_goal_id, org_goal_id, appraisal_id, parent_obj_id = _resolve_ids(db, org_id, payload)
    
    progress = _calculate_progress(payload.current_value, payload.target_value)
    
    db_item = EmployeeGoal(
        organization_id=org_id,
        employee_id=emp_id,
        framework_id=fw_id,
        parent_dept_goal_id=dept_goal_id,
        parent_org_goal_id=org_goal_id,
        appraisal_cycle_id=appraisal_id,
        parent_objective_id=parent_obj_id,
        title=payload.title,
        description=payload.description,
        start_date=payload.start_date,
        end_date=payload.end_date,
        measurement_type=payload.measurement_type,
        target_value=payload.target_value,
        current_value=payload.current_value,
        baseline_value=payload.baseline_value,
        unit=payload.unit,
        weight=payload.weight if payload.weight is not None else Decimal("100.00"),
        status=payload.status or GoalStatus.DRAFT,
        progress_percentage=progress,
        is_stretch_goal=payload.is_stretch_goal,
        is_specific=payload.is_specific,
        is_measurable=payload.is_measurable,
        is_achievable=payload.is_achievable,
        is_relevant=payload.is_relevant,
        is_time_bound=payload.is_time_bound,
        objective_key=payload.objective_key,
        is_key_result=payload.is_key_result,
        tags=payload.tags or [],
        created_by=current_user.id if not isinstance(current_user, Organization) else emp_id
    )
    
    db.add(db_item)
    db.commit()
    db.refresh(db_item)
    
    # Map to schema output
    schema_data = EmployeeGoalSchema.model_validate(db_item)
    if db_item.employee:
        schema_data.employee_name = f"{db_item.employee.first_name} {db_item.employee.last_name}".strip()
    if db_item.manager:
        schema_data.manager_name = f"{db_item.manager.first_name} {db_item.manager.last_name}".strip()
    if db_item.framework:
        schema_data.framework_name = db_item.framework.name
        
    return EmployeeGoalResponse(
        success=True,
        message="Employee goal created successfully",
        data=schema_data
    )

@router.put("/{goal_uuid}", response_model=EmployeeGoalResponse)
def update_employee_goal(
    goal_uuid: uuid.UUID,
    payload: EmployeeGoalUpdate,
    db: Session = Depends(deps.get_db),
    current_user: Union[Organization, Employee] = Depends(deps.get_current_user)
):
    org_id = _get_org_id(current_user)
    
    db_item = db.query(EmployeeGoal).filter(EmployeeGoal.is_deleted == False, 
        EmployeeGoal.uuid == goal_uuid,
        EmployeeGoal.organization_id == org_id
    ).first()
    
    if not db_item:
        raise HTTPException(status_code=404, detail="Employee goal not found")
        
    # RBAC checks
    if not isinstance(current_user, Organization):
        has_update = deps.has_permission(db, current_user, PerformancePermissions.UPDATE)
        if not has_update:
            if db_item.employee_id != current_user.id:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN, 
                    detail="You do not have permission to update goals for other employees."
                )
                
    emp_id, fw_id, dept_goal_id, org_goal_id, appraisal_id, parent_obj_id = _resolve_ids(db, org_id, payload)
    
    update_data = payload.dict(exclude_unset=True)
    
    if emp_id is not None:
        db_item.employee_id = emp_id
    if fw_id is not None:
        db_item.framework_id = fw_id
    if "parent_dept_goal_uuid" in update_data:
        db_item.parent_dept_goal_id = dept_goal_id
    if "parent_org_goal_uuid" in update_data:
        db_item.parent_org_goal_id = org_goal_id
    if "appraisal_cycle_uuid" in update_data:
        db_item.appraisal_cycle_id = appraisal_id
    if "parent_objective_uuid" in update_data:
        db_item.parent_objective_id = parent_obj_id
        
    for field in ["title", "description", "start_date", "end_date", "measurement_type", 
                  "target_value", "current_value", "baseline_value", "unit", "weight",
                  "status", "is_stretch_goal", "tags", "is_specific", "is_measurable",
                  "is_achievable", "is_relevant", "is_time_bound", "objective_key", "is_key_result"]:
        if field in update_data:
            setattr(db_item, field, update_data[field])
            
    if "current_value" in update_data or "target_value" in update_data:
        db_item.progress_percentage = _calculate_progress(db_item.current_value, db_item.target_value)
        
    db.commit()
    db.refresh(db_item)
    
    schema_data = EmployeeGoalSchema.model_validate(db_item)
    if db_item.employee:
        schema_data.employee_name = f"{db_item.employee.first_name} {db_item.employee.last_name}".strip()
    if db_item.manager:
        schema_data.manager_name = f"{db_item.manager.first_name} {db_item.manager.last_name}".strip()
    if db_item.framework:
        schema_data.framework_name = db_item.framework.name
        
    return EmployeeGoalResponse(
        success=True,
        message="Employee goal updated successfully",
        data=schema_data
    )

@router.delete("/{goal_uuid}")
def delete_employee_goal(
    goal_uuid: uuid.UUID,
    db: Session = Depends(deps.get_db),
    current_user: Union[Organization, Employee] = Depends(deps.get_current_user)
):
    org_id = _get_org_id(current_user)
    
    db_item = db.query(EmployeeGoal).filter(EmployeeGoal.is_deleted == False, 
        EmployeeGoal.uuid == goal_uuid,
        EmployeeGoal.organization_id == org_id
    ).first()
    
    if not db_item:
        raise HTTPException(status_code=404, detail="Employee goal not found")
        
    # RBAC checks
    if not isinstance(current_user, Organization):
        has_delete = deps.has_permission(db, current_user, PerformancePermissions.DELETE)
        if not has_delete:
            if db_item.employee_id != current_user.id:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN, 
                    detail="You do not have permission to delete goals for other employees."
                )
                
    db_item.is_deleted = True
    db.commit()
    
    return {
        "success": True,
        "message": "Employee goal deleted successfully",
        "data": None
    }

@router.get("/lookup", response_model=EmployeeGoalLookupResponse)
def lookup_employee_goals(
    employee_id: Optional[str] = None,
    manager_id: Optional[str] = None,
    appraisal_cycle_id: Optional[str] = None,
    status_filter: Optional[GoalStatus] = Query(None, alias="status"),
    framework_type: Optional[GoalFrameworkType] = None,
    is_stretch_goal: Optional[bool] = None,
    search: Optional[str] = Query(None),
    sort_by: Optional[str] = Query(None),
    sort_order: Optional[str] = Query('asc'),
    page: int = Query(1, ge=1),
    limit: int = Query(10, ge=1, le=100),
    db: Session = Depends(deps.get_db),
    current_user: Union[Organization, Employee] = Depends(deps.get_current_user)
):
    org_id = _get_org_id(current_user)
    
    query = db.query(EmployeeGoal).filter(EmployeeGoal.is_deleted == False, EmployeeGoal.organization_id == org_id)

    # Filters
    if employee_id:
        try:
            emp_uuid = uuid.UUID(str(employee_id))
            emp = db.query(Employee).filter(Employee.uuid == emp_uuid, Employee.organization_id == org_id).first()
        except ValueError:
            try:
                e_id = int(employee_id)
                emp = db.query(Employee).filter(Employee.id == e_id, Employee.organization_id == org_id).first()
            except ValueError:
                emp = None
        if emp:
            query = query.filter(EmployeeGoal.employee_id == emp.id)
        else:
            query = query.filter(EmployeeGoal.id == -1)

    if manager_id:
        try:
            mgr_uuid = uuid.UUID(str(manager_id))
            mgr = db.query(Employee).filter(Employee.uuid == mgr_uuid, Employee.organization_id == org_id).first()
        except ValueError:
            try:
                m_id = int(manager_id)
                mgr = db.query(Employee).filter(Employee.id == m_id, Employee.organization_id == org_id).first()
            except ValueError:
                mgr = None
        if mgr:
            query = query.filter(EmployeeGoal.manager_id == mgr.id)
        else:
            query = query.filter(EmployeeGoal.id == -1)

    if appraisal_cycle_id:
        try:
            ac_uuid = uuid.UUID(str(appraisal_cycle_id))
            from app.models.performance import AppraisalCycle
            ac = db.query(AppraisalCycle).filter(AppraisalCycle.uuid == ac_uuid, AppraisalCycle.organization_id == org_id).first()
        except ValueError:
            try:
                ac_id = int(appraisal_cycle_id)
                from app.models.performance import AppraisalCycle
                ac = db.query(AppraisalCycle).filter(AppraisalCycle.id == ac_id, AppraisalCycle.organization_id == org_id).first()
            except ValueError:
                ac = None
        if ac:
            query = query.filter(EmployeeGoal.appraisal_cycle_id == ac.id)
        else:
            query = query.filter(EmployeeGoal.id == -1)

    if status_filter:
        query = query.filter(EmployeeGoal.status == status_filter)

    if is_stretch_goal is not None:
        query = query.filter(EmployeeGoal.is_stretch_goal == is_stretch_goal)

    if framework_type:
        query = query.join(GoalFramework).filter(GoalFramework.framework_type == framework_type)

    if search:
        query = query.filter(
            or_(
                EmployeeGoal.title.ilike(f"%{search}%"),
                EmployeeGoal.description.ilike(f"%{search}%")
            )
        )

    total_records = query.count()
    
    if sort_by:
        sort_column = None
        if sort_by == 'title':
            sort_column = EmployeeGoal.title
        elif sort_by == 'progress_percentage':
            sort_column = EmployeeGoal.progress_percentage
        elif sort_by == 'status':
            sort_column = EmployeeGoal.status
        elif sort_by == 'start_date':
            sort_column = EmployeeGoal.start_date
        elif sort_by == 'end_date':
            sort_column = EmployeeGoal.end_date
            
        if sort_column is not None:
            if sort_order == 'desc':
                query = query.order_by(sort_column.desc())
            else:
                query = query.order_by(sort_column.asc())
        else:
            query = query.order_by(EmployeeGoal.id.desc())
    else:
        query = query.order_by(EmployeeGoal.id.desc())
        
    goals = query.offset((page - 1) * limit).limit(limit).all()
    
    # Map to schema output
    items = []
    for g in goals:
        lookup_item = EmployeeGoalLookupSchema(
            uuid=g.uuid,
            title=g.title,
            status=g.status,
            progress_percentage=g.progress_percentage,
            employee_name=f"{g.employee.first_name} {g.employee.last_name}".strip() if g.employee else None,
            employee_uuid=g.employee.uuid if g.employee else None
        )
        items.append(lookup_item)
    
    return EmployeeGoalLookupResponse(
        success=True,
        message="Employee goals lookup retrieved successfully",
        data=items,
        pagination={
            "total_records": total_records,
            "current_page": page,
            "total_pages": (total_records + limit - 1) // limit if total_records > 0 else 0,
            "page_size": limit
        }
    )

@router.get("/my-goals", response_model=MyGoalsDashboardResponse)
def get_my_goals_dashboard(
    appraisal_cycle_id: Optional[uuid.UUID] = None,
    status: Optional[str] = None,
    fiscal_year: Optional[str] = None,
    db: Session = Depends(deps.get_db),
    current_user: Union[Organization, Employee] = Depends(deps.get_current_user)
):
    if not isinstance(current_user, Employee):
        raise HTTPException(
            status_code=403, 
            detail="Only employees can access their own personal goals dashboard."
        )
        
    org_id = _get_org_id(current_user)
    
    query = db.query(EmployeeGoal).filter(
        EmployeeGoal.employee_id == current_user.id,
        EmployeeGoal.organization_id == org_id,
        EmployeeGoal.is_deleted == False
    )
    
    if appraisal_cycle_id:
        query = query.filter(EmployeeGoal.appraisal_cycle_id == appraisal_cycle_id)
    if status:
        query = query.filter(EmployeeGoal.status == status)
    if fiscal_year:
        query = query.filter(EmployeeGoal.fiscal_year == fiscal_year)
        
    goals = query.all()
    
    from collections import defaultdict
    groups_map = defaultdict(list)
    
    total_progress = 0
    
    for g in goals:
        framework_uuid = g.framework.uuid if g.framework else uuid.UUID(int=0)
        framework_name = g.framework.name if g.framework else "Uncategorized"
        total_progress += float(g.progress_percentage)
        groups_map[(framework_uuid, framework_name)].append(g)
        
    overall_completion = (total_progress / len(goals)) if len(goals) > 0 else 0.0
    
    groups_list = []
    for (fw_uuid, fw_name), fw_goals in groups_map.items():
        fw_progress = sum(float(x.progress_percentage) for x in fw_goals) / len(fw_goals)
        groups_list.append(MyGoalsGroup(
            framework_id=fw_uuid,
            framework_name=fw_name,
            overall_progress=fw_progress,
            goals=fw_goals
        ))
        
    return MyGoalsDashboardResponse(
        groups=groups_list,
        overall_completion_percentage=overall_completion
    )


@router.get("/{goal_uuid}", response_model=EmployeeGoalResponse)
def get_employee_goal(
    goal_uuid: uuid.UUID,
    db: Session = Depends(deps.get_db),
    current_user: Union[Organization, Employee] = Depends(deps.get_current_user)
):
    org_id = _get_org_id(current_user)
    
    db_item = db.query(EmployeeGoal).filter(EmployeeGoal.is_deleted == False, 
        EmployeeGoal.uuid == goal_uuid,
        EmployeeGoal.organization_id == org_id
    ).first()
    
    if not db_item:
        raise HTTPException(status_code=404, detail="Employee goal not found")
        
    # RBAC checks
    if not isinstance(current_user, Organization):
        has_read = deps.has_permission(db, current_user, PerformancePermissions.READ)
        if not has_read:
            # Can only read if they are the owner or manager
            if db_item.employee_id != current_user.id and db_item.manager_id != current_user.id:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN, 
                    detail="You do not have permission to view this goal."
                )
                
    schema_data = EmployeeGoalSchema.model_validate(db_item)
    if db_item.employee:
        schema_data.employee_name = f"{db_item.employee.first_name} {db_item.employee.last_name}".strip()
    if db_item.manager:
        schema_data.manager_name = f"{db_item.manager.first_name} {db_item.manager.last_name}".strip()
    if db_item.framework:
        schema_data.framework_name = db_item.framework.name
        
    return EmployeeGoalResponse(
        success=True,
        message="Employee goal retrieved successfully",
        data=schema_data
    )

@router.patch("/{goal_uuid}/approve", response_model=EmployeeGoalResponse)
def approve_employee_goal(
    goal_uuid: uuid.UUID,
    payload: GoalApprovalRequest,
    db: Session = Depends(deps.get_db),
    current_user: Union[Organization, Employee] = Depends(deps.get_current_user)
):
    org_id = _get_org_id(current_user)
    
    db_item = db.query(EmployeeGoal).filter(EmployeeGoal.is_deleted == False, 
        EmployeeGoal.uuid == goal_uuid,
        EmployeeGoal.organization_id == org_id
    ).first()
    
    if not db_item:
        raise HTTPException(status_code=404, detail="Employee goal not found")
        
    # RBAC checks
    if not isinstance(current_user, Organization):
        has_update = deps.has_permission(db, current_user, PerformancePermissions.UPDATE)
        if not has_update:
            # Must be the manager of this goal's employee
            if db_item.manager_id != current_user.id:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN, 
                    detail="You do not have permission to approve this goal."
                )
                
    db_item.approved_by = current_user.id
    db_item.approved_at = datetime.utcnow()
    if payload.manager_comment is not None:
        db_item.manager_comment = payload.manager_comment
        
    if payload.approved:
        db_item.status = GoalStatus.ACTIVE
        
    db.commit()
    db.refresh(db_item)
    
    schema_data = EmployeeGoalSchema.model_validate(db_item)
    if db_item.employee:
        schema_data.employee_name = f"{db_item.employee.first_name} {db_item.employee.last_name}".strip()
    if db_item.manager:
        schema_data.manager_name = f"{db_item.manager.first_name} {db_item.manager.last_name}".strip()
    if db_item.framework:
        schema_data.framework_name = db_item.framework.name
        
    return EmployeeGoalResponse(
        success=True,
        message="Employee goal approval status updated",
        data=schema_data
    )

@router.patch("/{goal_uuid}/status", response_model=EmployeeGoalResponse)
def update_employee_goal_status(
    goal_uuid: uuid.UUID,
    payload: GoalStatusUpdateRequest,
    db: Session = Depends(deps.get_db),
    current_user: Union[Organization, Employee] = Depends(deps.get_current_user)
):
    org_id = _get_org_id(current_user)
    
    db_item = db.query(EmployeeGoal).filter(EmployeeGoal.is_deleted == False, 
        EmployeeGoal.uuid == goal_uuid,
        EmployeeGoal.organization_id == org_id
    ).first()
    
    if not db_item:
        raise HTTPException(status_code=404, detail="Employee goal not found")
        
    # RBAC checks
    if not isinstance(current_user, Organization):
        has_update = deps.has_permission(db, current_user, PerformancePermissions.UPDATE)
        if not has_update:
            if db_item.employee_id != current_user.id and db_item.manager_id != current_user.id:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN, 
                    detail="You do not have permission to update status for this goal."
                )
                
    db_item.status = payload.status
    if payload.notes:
        timestamp = datetime.utcnow().strftime("%Y-%m-%d %H:%M")
        note_entry = f"\n\n[{timestamp} Status Update - {payload.status.value}]: {payload.notes}"
        db_item.description = (db_item.description or "") + note_entry
        
    db.commit()
    db.refresh(db_item)
    
    schema_data = EmployeeGoalSchema.model_validate(db_item)
    if db_item.employee:
        schema_data.employee_name = f"{db_item.employee.first_name} {db_item.employee.last_name}".strip()
    if db_item.manager:
        schema_data.manager_name = f"{db_item.manager.first_name} {db_item.manager.last_name}".strip()
    if db_item.framework:
        schema_data.framework_name = db_item.framework.name
        
    return EmployeeGoalResponse(
        success=True,
        message="Employee goal status updated",
        data=schema_data
    )





# ---------------------------------------------------------
# GOAL PROGRESS
# ---------------------------------------------------------

@router.get("/{goal_uuid}/progress", response_model=schema.GoalProgressListResponse)
def list_goal_progress(
    goal_uuid: uuid.UUID,
    from_date: Optional[date] = None,
    to_date: Optional[date] = None,
    page: int = Query(1, ge=1),
    limit: int = Query(10, ge=1, le=100),
    db: Session = Depends(deps.get_db),
    current_user: Union[Organization, Employee] = Depends(deps.get_current_user)
):
    org_id = _get_org_id(current_user)
    
    db_goal = db.query(EmployeeGoal).filter(
        EmployeeGoal.uuid == goal_uuid,
        EmployeeGoal.organization_id == org_id,
        EmployeeGoal.is_deleted == False
    ).first()
    
    if not db_goal:
        raise HTTPException(status_code=404, detail="Employee goal not found")
        
    if not isinstance(current_user, Organization):
        has_read = deps.has_permission(db, current_user, PerformancePermissions.READ)
        if not has_read and db_goal.employee_id != current_user.id:
            raise HTTPException(status_code=403, detail="Not authorized to view progress for this goal")
            
    query = db.query(GoalProgress).filter(GoalProgress.employee_goal_id == db_goal.id)
    
    if from_date:
        query = query.filter(GoalProgress.check_in_date >= from_date)
    if to_date:
        query = query.filter(GoalProgress.check_in_date <= to_date)
        
    total_records = query.count()
    total_pages = (total_records + limit - 1) // limit
    records = query.order_by(GoalProgress.check_in_date.desc()).offset((page - 1) * limit).limit(limit).all()
    
    return schema.GoalProgressListResponse(
        success=True,
        message="Goal progress entries fetched successfully",
        data=records,
        pagination=schema.Pagination(
            total_records=total_records,
            current_page=page,
            total_pages=total_pages,
            page_size=limit
        )
    )

@router.post("/{goal_uuid}/progress", response_model=schema.GoalProgressResponse)
def create_goal_progress(
    goal_uuid: uuid.UUID,
    payload: schema.GoalProgressCreate,
    db: Session = Depends(deps.get_db),
    current_user: Union[Organization, Employee] = Depends(deps.get_current_user)
):
    org_id = _get_org_id(current_user)
    
    db_goal = db.query(EmployeeGoal).filter(
        EmployeeGoal.uuid == goal_uuid,
        EmployeeGoal.organization_id == org_id,
        EmployeeGoal.is_deleted == False
    ).first()
    
    if not db_goal:
        raise HTTPException(status_code=404, detail="Employee goal not found")
        
    if not isinstance(current_user, Organization):
        has_update = deps.has_permission(db, current_user, PerformancePermissions.UPDATE)
        if not has_update and db_goal.employee_id != current_user.id:
            raise HTTPException(status_code=403, detail="Not authorized to update this goal")
            
    # Create progress log
    progress = GoalProgress(
        employee_goal_id=db_goal.id,
        employee_id=db_goal.employee_id,
        check_in_date=payload.check_in_date,
        current_value=payload.current_value,
        progress_percentage=payload.progress_percentage,
        status=payload.status,
        update_notes=payload.update_notes,
        blockers=payload.blockers,
        next_steps=payload.next_steps,
        attachments=payload.attachments or []
    )
    
    db.add(progress)
    
    # Auto-update the parent goal
    db_goal.current_value = payload.current_value
    db_goal.progress_percentage = payload.progress_percentage
    db_goal.status = payload.status
    
    db.commit()
    db.refresh(progress)
    
    return schema.GoalProgressResponse(
        success=True,
        message="Goal progress logged successfully",
        data=progress
    )

@router.get("/{goal_uuid}/progress/{progress_uuid}", response_model=schema.GoalProgressResponse)
def get_goal_progress(
    goal_uuid: uuid.UUID,
    progress_uuid: uuid.UUID,
    db: Session = Depends(deps.get_db),
    current_user: Union[Organization, Employee] = Depends(deps.get_current_user)
):
    org_id = _get_org_id(current_user)
    
    db_goal = db.query(EmployeeGoal).filter(
        EmployeeGoal.uuid == goal_uuid,
        EmployeeGoal.organization_id == org_id,
        EmployeeGoal.is_deleted == False
    ).first()
    
    if not db_goal:
        raise HTTPException(status_code=404, detail="Employee goal not found")
        
    if not isinstance(current_user, Organization):
        has_read = deps.has_permission(db, current_user, PerformancePermissions.READ)
        if not has_read and db_goal.employee_id != current_user.id:
            raise HTTPException(status_code=403, detail="Not authorized to view progress for this goal")
            
    progress = db.query(GoalProgress).filter(
        GoalProgress.uuid == progress_uuid,
        GoalProgress.employee_goal_id == db_goal.id
    ).first()
    
    if not progress:
        raise HTTPException(status_code=404, detail="Progress log not found")
        
    return schema.GoalProgressResponse(
        success=True,
        message="Goal progress fetched successfully",
        data=progress
    )

@router.put("/{goal_uuid}/progress/{progress_uuid}", response_model=schema.GoalProgressResponse)
def update_goal_progress(
    goal_uuid: uuid.UUID,
    progress_uuid: uuid.UUID,
    payload: schema.GoalProgressUpdate,
    db: Session = Depends(deps.get_db),
    current_user: Union[Organization, Employee] = Depends(deps.get_current_user)
):
    org_id = _get_org_id(current_user)
    
    db_goal = db.query(EmployeeGoal).filter(
        EmployeeGoal.uuid == goal_uuid,
        EmployeeGoal.organization_id == org_id,
        EmployeeGoal.is_deleted == False
    ).first()
    
    if not db_goal:
        raise HTTPException(status_code=404, detail="Employee goal not found")
        
    if not isinstance(current_user, Organization):
        has_update = deps.has_permission(db, current_user, PerformancePermissions.UPDATE)
        if not has_update and db_goal.employee_id != current_user.id:
            raise HTTPException(status_code=403, detail="Not authorized to update this goal")
            
    progress = db.query(GoalProgress).filter(
        GoalProgress.uuid == progress_uuid,
        GoalProgress.employee_goal_id == db_goal.id
    ).first()
    
    if not progress:
        raise HTTPException(status_code=404, detail="Progress log not found")
        
    if progress.acknowledged_by is not None:
        raise HTTPException(status_code=400, detail="Cannot edit a progress log that has already been acknowledged by a manager")
        
    update_data = payload.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(progress, key, value)
        
    # If the latest progress was edited, should we update the parent goal? Yes, we assume this is the latest.
    latest_progress = db.query(GoalProgress).filter(GoalProgress.employee_goal_id == db_goal.id).order_by(GoalProgress.check_in_date.desc(), GoalProgress.id.desc()).first()
    if latest_progress and latest_progress.id == progress.id:
        if payload.current_value is not None: db_goal.current_value = payload.current_value
        if payload.progress_percentage is not None: db_goal.progress_percentage = payload.progress_percentage
        if payload.status is not None: db_goal.status = payload.status
        
    db.commit()
    db.refresh(progress)
    
    return schema.GoalProgressResponse(
        success=True,
        message="Goal progress updated successfully",
        data=progress
    )

@router.patch("/{goal_uuid}/progress/{progress_uuid}/acknowledge", response_model=schema.GoalProgressResponse)
def acknowledge_goal_progress(
    goal_uuid: uuid.UUID,
    progress_uuid: uuid.UUID,
    payload: schema.GoalProgressAcknowledge,
    db: Session = Depends(deps.get_db),
    current_user: Union[Organization, Employee] = Depends(deps.get_current_user)
):
    org_id = _get_org_id(current_user)
    
    db_goal = db.query(EmployeeGoal).filter(
        EmployeeGoal.uuid == goal_uuid,
        EmployeeGoal.organization_id == org_id,
        EmployeeGoal.is_deleted == False
    ).first()
    
    if not db_goal:
        raise HTTPException(status_code=404, detail="Employee goal not found")
        
    if not isinstance(current_user, Organization):
        has_update = deps.has_permission(db, current_user, PerformancePermissions.UPDATE)
        if not has_update:
            raise HTTPException(status_code=403, detail="Only authorized managers can acknowledge goal progress")
            
    progress = db.query(GoalProgress).filter(
        GoalProgress.uuid == progress_uuid,
        GoalProgress.employee_goal_id == db_goal.id
    ).first()
    
    if not progress:
        raise HTTPException(status_code=404, detail="Progress log not found")
        
    progress.acknowledged_by = current_user.id if isinstance(current_user, Employee) else None
    progress.acknowledged_at = datetime.utcnow()
    progress.manager_comment = payload.manager_comment
    
    db.commit()
    db.refresh(progress)
    
    return schema.GoalProgressResponse(
        success=True,
        message="Goal progress acknowledged successfully",
        data=progress
    )

@router.delete("/{goal_uuid}/progress/{progress_uuid}")
def delete_goal_progress(
    goal_uuid: uuid.UUID,
    progress_uuid: uuid.UUID,
    db: Session = Depends(deps.get_db),
    current_user: Union[Organization, Employee] = Depends(deps.get_current_user)
):
    org_id = _get_org_id(current_user)
    
    db_goal = db.query(EmployeeGoal).filter(
        EmployeeGoal.uuid == goal_uuid,
        EmployeeGoal.organization_id == org_id,
        EmployeeGoal.is_deleted == False
    ).first()
    
    if not db_goal:
        raise HTTPException(status_code=404, detail="Employee goal not found")
        
    if not isinstance(current_user, Organization):
        has_delete = deps.has_permission(db, current_user, PerformancePermissions.DELETE)
        if not has_delete and db_goal.employee_id != current_user.id:
            raise HTTPException(status_code=403, detail="Not authorized to delete progress logs for this goal")
            
    progress = db.query(GoalProgress).filter(
        GoalProgress.uuid == progress_uuid,
        GoalProgress.employee_goal_id == db_goal.id
    ).first()
    
    if not progress:
        raise HTTPException(status_code=404, detail="Progress log not found")
        
    if progress.acknowledged_by is not None:
        raise HTTPException(status_code=400, detail="Cannot delete a progress log that has already been acknowledged")
        
    db.delete(progress)
    db.commit()
    
    return {"success": True, "message": "Goal progress deleted successfully"}

