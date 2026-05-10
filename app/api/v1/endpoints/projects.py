from typing import Optional, Union
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import func, or_
import uuid
from datetime import datetime

from app.api import deps
from app.models.organization import Organization
from app.models.employee import Employee
from app.models.projects import Project, ProjectClient, ProjectMember, ProjectTask, ProjectStatus, ProjectType
from app.schemas.projects import (
    ProjectCreate, ProjectUpdate, ProjectSchema, ProjectDetailSchema, ProjectResponse, ProjectListResponse,
    ProjectMemberCreate, ProjectMemberUpdate, ProjectMemberSchema,
    ProjectMemberResponse, ProjectMemberListResponse,
    ProjectEmployeeViewSchema, ProjectEmployeeViewListResponse
)

router = APIRouter()


def _require(db, user, code, action):
    if isinstance(user, Organization):
        return
    if not deps.has_permission(db, user, code):
        raise HTTPException(status_code=403, detail=f"No permission to {action} projects (code: {code})")


def _org_id(user):
    return user.id if isinstance(user, Organization) else user.organization_id


def _resolve_employee(db, emp_uuid, org_id, label="Employee"):
    emp = db.query(Employee).filter(Employee.uuid == emp_uuid, Employee.organization_id == org_id).first()
    if not emp:
        raise HTTPException(status_code=404, detail=f"{label} not found")
    return emp


# -------------------------------------------------------
# LOOKUP — open (auth only)
# -------------------------------------------------------
@router.get("/lookup")
def lookup_projects(
    db: Session = Depends(deps.get_db),
    current_user: Union[Organization, Employee] = Depends(deps.get_current_user),
    search: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    limit: int = Query(100, ge=1, le=200),
    assigned_only: bool = Query(False, description="Only return projects the employee is a member of"),
    employee_uuid: Optional[uuid.UUID] = Query(None, description="Filter by employee membership")
):
    """Open lookup for dropdowns. No RBAC required."""
    org_id = _org_id(current_user)
    query = db.query(Project).filter(
        Project.organization_id == org_id,
        Project.is_active == True,
        Project.is_deleted == False
    )
    if status:
        query = query.filter(Project.status == status)
    if search:
        query = query.filter(Project.project_name.ilike(f"%{search}%"))

    # Membership Filtering
    target_employee_id = None
    if employee_uuid:
        emp = _resolve_employee(db, employee_uuid, org_id)
        target_employee_id = emp.id
    elif assigned_only and isinstance(current_user, Employee):
        target_employee_id = current_user.id

    if target_employee_id:
        query = query.join(ProjectMember, ProjectMember.project_id == Project.id).filter(
            ProjectMember.employee_id == target_employee_id,
            ProjectMember.is_active == True
        )

    projects = query.order_by(Project.project_name).limit(limit).all()
    return {
        "success": True,
        "data": [
            {
                "uuid": p.uuid, 
                "project_name": p.project_name, 
                "project_code": p.project_code, 
                "status": p.status, 
                "project_type": p.project_type,
                "client_uuid": p.client.uuid if p.client else None
            } for p in projects
        ]
    }


@router.get("/assigned", response_model=ProjectEmployeeViewListResponse)
def get_assigned_projects(
    employee_uuid: Optional[uuid.UUID] = Query(None, description="Employee UUID. If not provided, returns projects for the current logged-in employee."),
    search: Optional[str] = Query(None),
    status: Optional[ProjectStatus] = Query(None),
    project_type: Optional[ProjectType] = Query(None),
    sort_by: str = Query("project_name", pattern="^(project_code|project_name|project_type|status|priority)$"),
    sort_order: str = Query("asc", pattern="^(asc|desc)$"),
    page: int = Query(1, ge=1),
    limit: int = Query(10, ge=1, le=100),
    db: Session = Depends(deps.get_db),
    current_user: Union[Organization, Employee] = Depends(deps.get_current_user)
):
    """
    Get list of projects assigned to an employee with searching, filtering, and pagination.
    Does NOT include financial, billing, or accounting details.
    """
    org_id = _org_id(current_user)
    
    # 1. Resolve Target Employee
    target_employee_id = None
    if employee_uuid:
        emp = _resolve_employee(db, employee_uuid, org_id)
        target_employee_id = emp.id
    elif isinstance(current_user, Employee):
        target_employee_id = current_user.id
    else:
        raise HTTPException(status_code=400, detail="employee_uuid is required for organization users")

    # 2. Build Query
    query = db.query(ProjectMember).join(Project).options(
        joinedload(ProjectMember.project).joinedload(Project.client),
        joinedload(ProjectMember.project).joinedload(Project.project_manager)
    ).filter(
        ProjectMember.employee_id == target_employee_id,
        ProjectMember.is_active == True,
        Project.is_deleted == False,
        Project.organization_id == org_id
    )

    # 3. Apply Filters
    if status:
        query = query.filter(Project.status == status)
    if project_type:
        query = query.filter(Project.project_type == project_type)
    if search:
        query = query.filter(
            or_(
                Project.project_name.ilike(f"%{search}%"),
                Project.project_code.ilike(f"%{search}%")
            )
        )

    # 4. Apply Sorting
    sort_attr = getattr(Project, sort_by)
    if sort_order == "desc":
        query = query.order_by(sort_attr.desc())
    else:
        query = query.order_by(sort_attr.asc())

    # 5. Pagination
    total_records = query.count()
    total_pages = (total_records + limit - 1) // limit
    
    members = query.offset((page - 1) * limit).limit(limit).all()

    # 6. Format Response
    data = []
    for member in members:
        p = member.project
        data.append(ProjectEmployeeViewSchema(
            uuid=p.uuid,
            project_code=p.project_code,
            project_name=p.project_name,
            description=p.description,
            project_type=p.project_type,
            status=p.status,
            priority=p.priority,
            start_date=p.start_date,
            end_date=p.end_date,
            color_code=p.color_code,
            tags=p.tags,
            client_name=p.client.client_name if p.client else None,
            project_manager_name=p.project_manager.full_name if p.project_manager else None,
            role=member.role
        ))

    return ProjectEmployeeViewListResponse(
        success=True,
        message="Assigned projects retrieved successfully",
        data=data,
        pagination={
            "total_records": total_records,
            "current_page": page,
            "total_pages": total_pages,
            "page_size": limit
        }
    )


# -------------------------------------------------------
# LIST — Permission 83
# -------------------------------------------------------
@router.get("/", response_model=ProjectListResponse)
def list_projects(
    db: Session = Depends(deps.get_db),
    current_user: Union[Organization, Employee] = Depends(deps.get_current_user),
    search: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    project_type: Optional[str] = Query(None),
    client_uuid: Optional[uuid.UUID] = Query(None),
    is_active: Optional[bool] = Query(None),
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    sort_by: Optional[str] = Query("created_at"),
    sort_order: Optional[str] = Query("desc")
):
    _require(db, current_user, "83", "list")
    org_id = _org_id(current_user)

    query = db.query(Project).filter(
        Project.organization_id == org_id,
        Project.is_deleted == False
    )
    if search:
        query = query.filter(Project.project_name.ilike(f"%{search}%"))
    if status:
        query = query.filter(Project.status == status)
    if project_type:
        query = query.filter(Project.project_type == project_type)
    if is_active is not None:
        query = query.filter(Project.is_active == is_active)
    if client_uuid:
        client = db.query(ProjectClient).filter(ProjectClient.uuid == client_uuid, ProjectClient.organization_id == org_id).first()
        if client:
            query = query.filter(Project.client_id == client.id)

    # Sorting logic
    sort_column = getattr(Project, sort_by, Project.created_at) if sort_by in ["project_code", "project_name", "status", "created_at"] else Project.created_at
    if sort_order == "desc":
        query = query.order_by(sort_column.desc())
    else:
        query = query.order_by(sort_column.asc())

    total = query.count()
    projects = query.offset((page - 1) * limit).limit(limit).all()

    return ProjectListResponse(
        success=True, message="Projects retrieved successfully",
        data=[ProjectSchema.model_validate(p) for p in projects],
        pagination={"total_records": total, "current_page": page, "total_pages": (total + limit - 1) // limit, "page_size": limit}
    )


# -------------------------------------------------------
# GET DETAIL — Permission 83
# -------------------------------------------------------
@router.get("/{project_uuid}", response_model=ProjectResponse)
def get_project(
    project_uuid: uuid.UUID,
    db: Session = Depends(deps.get_db),
    current_user: Union[Organization, Employee] = Depends(deps.get_current_user)
):
    _require(db, current_user, "83", "view")
    project = db.query(Project).options(
        joinedload(Project.client),
        joinedload(Project.project_manager)
    ).filter(
        Project.uuid == project_uuid,
        Project.organization_id == _org_id(current_user),
        Project.is_deleted == False
    ).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    return ProjectResponse(success=True, message="Project retrieved", data=ProjectDetailSchema.model_validate(project))


# -------------------------------------------------------
# CREATE — Permission 84
# -------------------------------------------------------
@router.post("/", response_model=ProjectResponse, status_code=status.HTTP_201_CREATED)
def create_project(
    project_in: ProjectCreate,
    db: Session = Depends(deps.get_db),
    current_user: Union[Organization, Employee] = Depends(deps.get_current_user)
):
    _require(db, current_user, "84", "create")
    org_id = _org_id(current_user)

    if db.query(Project).filter(
        Project.organization_id == org_id,
        Project.project_code == project_in.project_code,
        Project.is_deleted == False
    ).first():
        raise HTTPException(status_code=400, detail=f"Project code '{project_in.project_code}' already exists")

    client_id = None
    if project_in.client_uuid:
        client = db.query(ProjectClient).filter(
            ProjectClient.uuid == project_in.client_uuid,
            ProjectClient.organization_id == org_id
        ).first()
        if not client:
            raise HTTPException(status_code=404, detail="Client not found")
        client_id = client.id

    manager_id = None
    if project_in.project_manager_uuid:
        mgr = _resolve_employee(db, project_in.project_manager_uuid, org_id, "Project manager")
        manager_id = mgr.id

    employee_id = current_user.id if isinstance(current_user, Employee) else None
    data = project_in.model_dump(exclude={"client_uuid", "project_manager_uuid", "department_uuid"})
    project = Project(
        organization_id=org_id,
        client_id=client_id,
        project_manager_id=manager_id,
        created_by=employee_id,
        **data
    )
    db.add(project)
    db.commit()
    db.refresh(project)
    return ProjectResponse(success=True, message="Project created successfully", data=ProjectSchema.model_validate(project))


# -------------------------------------------------------
# UPDATE — Permission 85
# -------------------------------------------------------
@router.put("/{project_uuid}", response_model=ProjectResponse)
def update_project(
    project_uuid: uuid.UUID,
    project_in: ProjectUpdate,
    db: Session = Depends(deps.get_db),
    current_user: Union[Organization, Employee] = Depends(deps.get_current_user)
):
    _require(db, current_user, "85", "update")
    org_id = _org_id(current_user)
    project = db.query(Project).filter(
        Project.uuid == project_uuid,
        Project.organization_id == org_id,
        Project.is_deleted == False
    ).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    data = project_in.model_dump(exclude_unset=True, exclude={"client_uuid", "project_manager_uuid"})
    for field, value in data.items():
        setattr(project, field, value)

    if project_in.client_uuid is not None:
        client = db.query(ProjectClient).filter(ProjectClient.uuid == project_in.client_uuid, ProjectClient.organization_id == org_id).first()
        if not client:
            raise HTTPException(status_code=404, detail="Client not found")
        project.client_id = client.id

    if project_in.project_manager_uuid is not None:
        mgr = _resolve_employee(db, project_in.project_manager_uuid, org_id, "Project manager")
        project.project_manager_id = mgr.id

    db.commit()
    db.refresh(project)
    return ProjectResponse(success=True, message="Project updated successfully", data=ProjectSchema.model_validate(project))


# -------------------------------------------------------
# DELETE — Permission 86
# -------------------------------------------------------
@router.delete("/{project_uuid}")
def delete_project(
    project_uuid: uuid.UUID,
    db: Session = Depends(deps.get_db),
    current_user: Union[Organization, Employee] = Depends(deps.get_current_user)
):
    _require(db, current_user, "86", "delete")
    project = db.query(Project).filter(
        Project.uuid == project_uuid,
        Project.organization_id == _org_id(current_user),
        Project.is_deleted == False
    ).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    project.is_deleted = True
    project.deleted_at = datetime.utcnow()
    project.is_active = False
    db.commit()
    return {"success": True, "message": "Project deleted successfully"}


# ============================================================
# PROJECT MEMBERS — sub-resource
# ============================================================

@router.get("/{project_uuid}/members", response_model=ProjectMemberListResponse)
def list_project_members(
    project_uuid: uuid.UUID,
    db: Session = Depends(deps.get_db),
    current_user: Union[Organization, Employee] = Depends(deps.get_current_user)
):
    """List members of a project. No RBAC required for lookup purposes."""
    project = db.query(Project).filter(Project.uuid == project_uuid, Project.organization_id == _org_id(current_user), Project.is_deleted == False).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    members = db.query(ProjectMember).options(joinedload(ProjectMember.employee)).filter(ProjectMember.project_id == project.id, ProjectMember.is_active == True).all()
    return ProjectMemberListResponse(success=True, message="Members retrieved", data=[ProjectMemberSchema.model_validate(m) for m in members])


@router.post("/{project_uuid}/members", response_model=ProjectMemberResponse, status_code=status.HTTP_201_CREATED)
def add_project_member(
    project_uuid: uuid.UUID,
    member_in: ProjectMemberCreate,
    db: Session = Depends(deps.get_db),
    current_user: Union[Organization, Employee] = Depends(deps.get_current_user)
):
    _require(db, current_user, "91", "manage members of")
    org_id = _org_id(current_user)
    project = db.query(Project).filter(Project.uuid == project_uuid, Project.organization_id == org_id, Project.is_deleted == False).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    employee = _resolve_employee(db, member_in.employee_uuid, org_id)

    existing = db.query(ProjectMember).filter(ProjectMember.project_id == project.id, ProjectMember.employee_id == employee.id).first()
    if existing:
        if existing.is_active:
            raise HTTPException(status_code=400, detail="Employee is already a member of this project")
        # Re-activate if previously removed
        existing.is_active = True
        existing.role = member_in.role
        existing.billing_rate = member_in.billing_rate
        existing.allocated_hours = member_in.allocated_hours
        existing.joined_at = member_in.joined_at
        existing.left_at = None
        db.commit()
        db.refresh(existing)
        return ProjectMemberResponse(success=True, message="Member re-activated", data=ProjectMemberSchema.model_validate(existing))

    employee_id = current_user.id if isinstance(current_user, Employee) else None
    member = ProjectMember(
        project_id=project.id,
        employee_id=employee.id,
        role=member_in.role,
        billing_rate=member_in.billing_rate,
        allocated_hours=member_in.allocated_hours,
        joined_at=member_in.joined_at,
        created_by=employee_id
    )
    db.add(member)
    db.commit()
    db.refresh(member)
    return ProjectMemberResponse(success=True, message="Member added successfully", data=ProjectMemberSchema.model_validate(member))


@router.put("/{project_uuid}/members/{member_uuid}", response_model=ProjectMemberResponse)
def update_project_member(
    project_uuid: uuid.UUID,
    member_uuid: uuid.UUID,
    member_in: ProjectMemberUpdate,
    db: Session = Depends(deps.get_db),
    current_user: Union[Organization, Employee] = Depends(deps.get_current_user)
):
    _require(db, current_user, "91", "manage members of")
    project = db.query(Project).filter(Project.uuid == project_uuid, Project.organization_id == _org_id(current_user), Project.is_deleted == False).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    member = db.query(ProjectMember).filter(ProjectMember.uuid == member_uuid, ProjectMember.project_id == project.id).first()
    if not member:
        raise HTTPException(status_code=404, detail="Member not found")

    for field, value in member_in.model_dump(exclude_unset=True).items():
        setattr(member, field, value)
    db.commit()
    db.refresh(member)
    return ProjectMemberResponse(success=True, message="Member updated", data=ProjectMemberSchema.model_validate(member))
