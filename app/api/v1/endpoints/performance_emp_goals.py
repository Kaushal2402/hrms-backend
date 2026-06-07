import uuid
from typing import List, Optional, Union
from decimal import Decimal
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from sqlalchemy import or_

from app.api import deps
from app.models.organization import Organization
from app.models.employee import Employee
from app.models.performance import EmployeeGoal, GoalFramework, GoalStatus, GoalFrameworkType
from app.schemas.performance_emp_goals import EmployeeGoalListResponse, EmployeeGoalSchema, EmployeeGoalCreate, EmployeeGoalResponse

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
        po = db.query(EmployeeGoal).filter(EmployeeGoal.uuid == payload.parent_objective_uuid, EmployeeGoal.organization_id == org_id).first()
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
    
    query = db.query(EmployeeGoal).filter(EmployeeGoal.organization_id == org_id)

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
        tags=payload.tags or []
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
