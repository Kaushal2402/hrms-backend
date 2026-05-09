from typing import Optional, Union
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import func
import uuid
from datetime import datetime
from decimal import Decimal

from app.api import deps
from app.models.organization import Organization
from app.models.employee import Employee
from app.models.projects import Project, ProjectTask, ProjectMember
from app.schemas.projects import (
    ProjectTaskCreate, ProjectTaskUpdate, ProjectTaskSchema, ProjectTaskDetailSchema,
    ProjectTaskResponse, ProjectTaskListResponse
)

router = APIRouter()


def _require(db, user, code, action):
    if isinstance(user, Organization):
        return
    if not deps.has_permission(db, user, code):
        raise HTTPException(status_code=403, detail=f"No permission to {action} tasks (code: {code})")


def _org_id(user):
    return user.id if isinstance(user, Organization) else user.organization_id


def _get_project(db, project_uuid, org_id):
    project = db.query(Project).filter(
        Project.uuid == project_uuid,
        Project.organization_id == org_id,
        Project.is_deleted == False
    ).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    return project


# -------------------------------------------------------
# LOOKUP — open (auth only), filtered by project
# -------------------------------------------------------
@router.get("/lookup")
def lookup_tasks(
    db: Session = Depends(deps.get_db),
    current_user: Union[Organization, Employee] = Depends(deps.get_current_user),
    project_uuid: Optional[uuid.UUID] = Query(None, description="Filter by project UUID"),
    search: Optional[str] = Query(None),
    limit: int = Query(100, ge=1, le=200)
):
    """Open lookup for timesheet entry dropdowns. No RBAC required."""
    org_id = _org_id(current_user)
    query = db.query(ProjectTask).filter(
        ProjectTask.organization_id == org_id,
        ProjectTask.is_deleted == False
    )
    if project_uuid:
        project = db.query(Project).filter(Project.uuid == project_uuid, Project.organization_id == org_id).first()
        if project:
            query = query.filter(ProjectTask.project_id == project.id)
    if search:
        query = query.filter(ProjectTask.task_name.ilike(f"%{search}%"))

    tasks = query.order_by(ProjectTask.task_name).limit(limit).all()
    return {
        "success": True,
        "data": [{"uuid": t.uuid, "task_name": t.task_name, "task_code": t.task_code, "status": t.status, "project_uuid": t.project.uuid} for t in tasks]
    }


# -------------------------------------------------------
# LIST ALL — Permission 87
# -------------------------------------------------------
@router.get("/", response_model=ProjectTaskListResponse)
def list_tasks(
    db: Session = Depends(deps.get_db),
    current_user: Union[Organization, Employee] = Depends(deps.get_current_user),
    project_uuid: Optional[uuid.UUID] = Query(None),
    status: Optional[str] = Query(None),
    assigned_to_uuid: Optional[uuid.UUID] = Query(None),
    search: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    sort_by: Optional[str] = Query("created_at"),
    sort_order: Optional[str] = Query("desc")
):
    _require(db, current_user, "87", "list")
    org_id = _org_id(current_user)

    query = db.query(ProjectTask).filter(
        ProjectTask.organization_id == org_id,
        ProjectTask.is_deleted == False
    )
    if project_uuid:
        project = db.query(Project).filter(Project.uuid == project_uuid, Project.organization_id == org_id).first()
        if project:
            query = query.filter(ProjectTask.project_id == project.id)
    if status:
        query = query.filter(ProjectTask.status == status)
    if search:
        query = query.filter(ProjectTask.task_name.ilike(f"%{search}%"))
    if assigned_to_uuid:
        emp = db.query(Employee).filter(Employee.uuid == assigned_to_uuid, Employee.organization_id == org_id).first()
        if emp:
            query = query.filter(ProjectTask.assigned_to_id == emp.id)

    total = query.count()
    
    # Dynamic Sorting
    valid_sort_columns = ["task_name", "task_code", "status", "created_at"]
    sort_column = sort_by if sort_by in valid_sort_columns else "created_at"
    order_col = getattr(ProjectTask, sort_column)
    if sort_order == "asc":
        query = query.order_by(order_col.asc())
    else:
        query = query.order_by(order_col.desc())
        
    tasks = query.options(
        joinedload(ProjectTask.project),
        joinedload(ProjectTask.assigned_to)
    ).offset((page - 1) * limit).limit(limit).all()

    return ProjectTaskListResponse(
        success=True, message="Tasks retrieved successfully",
        data=[ProjectTaskDetailSchema.model_validate(t) for t in tasks],
        pagination={"total_records": total, "current_page": page, "total_pages": (total + limit - 1) // limit, "page_size": limit}
    )


# -------------------------------------------------------
# GET DETAIL — Permission 87
# -------------------------------------------------------
@router.get("/{task_uuid}", response_model=ProjectTaskResponse)
def get_task(
    task_uuid: uuid.UUID,
    db: Session = Depends(deps.get_db),
    current_user: Union[Organization, Employee] = Depends(deps.get_current_user)
):
    _require(db, current_user, "87", "view")
    task = db.query(ProjectTask).options(
        joinedload(ProjectTask.project),
        joinedload(ProjectTask.assigned_to)
    ).filter(
        ProjectTask.uuid == task_uuid,
        ProjectTask.organization_id == _org_id(current_user),
        ProjectTask.is_deleted == False
    ).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    return ProjectTaskResponse(success=True, message="Task retrieved", data=ProjectTaskDetailSchema.model_validate(task))


# -------------------------------------------------------
# CREATE — Permission 88
# -------------------------------------------------------
@router.post("/", response_model=ProjectTaskResponse, status_code=status.HTTP_201_CREATED)
def create_task(
    task_in: ProjectTaskCreate,
    db: Session = Depends(deps.get_db),
    current_user: Union[Organization, Employee] = Depends(deps.get_current_user)
):
    _require(db, current_user, "88", "create")
    org_id = _org_id(current_user)
    project = _get_project(db, task_in.project_uuid, org_id)

    assigned_to_id = None
    if task_in.assigned_to_uuid:
        emp = db.query(Employee).filter(Employee.uuid == task_in.assigned_to_uuid, Employee.organization_id == org_id).first()
        if not emp:
            raise HTTPException(status_code=404, detail="Assigned employee not found")
        assigned_to_id = emp.id

    parent_task_id = None
    if task_in.parent_task_uuid:
        parent = db.query(ProjectTask).filter(ProjectTask.uuid == task_in.parent_task_uuid, ProjectTask.project_id == project.id).first()
        if not parent:
            raise HTTPException(status_code=404, detail="Parent task not found")
        parent_task_id = parent.id

    employee_id = current_user.id if isinstance(current_user, Employee) else None
    data = task_in.model_dump(exclude={"project_uuid", "assigned_to_uuid", "parent_task_uuid"})
    task = ProjectTask(
        organization_id=org_id,
        project_id=project.id,
        assigned_to_id=assigned_to_id,
        parent_task_id=parent_task_id,
        created_by=employee_id,
        **data
    )
    db.add(task)
    db.commit()
    db.refresh(task)
    return ProjectTaskResponse(success=True, message="Task created successfully", data=ProjectTaskSchema.model_validate(task))


# -------------------------------------------------------
# UPDATE — Permission 89
# -------------------------------------------------------
@router.put("/{task_uuid}", response_model=ProjectTaskResponse)
def update_task(
    task_uuid: uuid.UUID,
    task_in: ProjectTaskUpdate,
    db: Session = Depends(deps.get_db),
    current_user: Union[Organization, Employee] = Depends(deps.get_current_user)
):
    _require(db, current_user, "89", "update")
    org_id = _org_id(current_user)
    task = db.query(ProjectTask).filter(
        ProjectTask.uuid == task_uuid,
        ProjectTask.organization_id == org_id,
        ProjectTask.is_deleted == False
    ).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    data = task_in.model_dump(exclude_unset=True, exclude={"assigned_to_uuid"})
    for field, value in data.items():
        setattr(task, field, value)

    if task_in.assigned_to_uuid is not None:
        emp = db.query(Employee).filter(Employee.uuid == task_in.assigned_to_uuid, Employee.organization_id == org_id).first()
        if not emp:
            raise HTTPException(status_code=404, detail="Assigned employee not found")
        task.assigned_to_id = emp.id

    # Auto-set completed_at when status → done
    if task_in.status and task_in.status.value == "done" and not task.completed_at:
        task.completed_at = datetime.utcnow()

    db.commit()
    db.refresh(task)
    return ProjectTaskResponse(success=True, message="Task updated successfully", data=ProjectTaskSchema.model_validate(task))


# -------------------------------------------------------
# DELETE — Permission 90
# -------------------------------------------------------
@router.delete("/{task_uuid}")
def delete_task(
    task_uuid: uuid.UUID,
    db: Session = Depends(deps.get_db),
    current_user: Union[Organization, Employee] = Depends(deps.get_current_user)
):
    _require(db, current_user, "90", "delete")
    task = db.query(ProjectTask).filter(
        ProjectTask.uuid == task_uuid,
        ProjectTask.organization_id == _org_id(current_user),
        ProjectTask.is_deleted == False
    ).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    task.is_deleted = True
    task.deleted_at = datetime.utcnow()
    db.commit()
    return {"success": True, "message": "Task deleted successfully"}
