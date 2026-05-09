from typing import Optional, Union
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from sqlalchemy import func
import uuid
from datetime import datetime

from app.api import deps
from app.models.organization import Organization
from app.models.employee import Employee
from app.models.projects import ProjectClient
from app.schemas.projects import (
    ProjectClientCreate, ProjectClientUpdate, ProjectClientSchema,
    ProjectClientResponse, ProjectClientListResponse
)

router = APIRouter()


def _require(db, user, code, action):
    if isinstance(user, Organization):
        return
    if not deps.has_permission(db, user, code):
        raise HTTPException(status_code=403, detail=f"No permission to {action} clients (code: {code})")


def _org_id(user):
    return user.id if isinstance(user, Organization) else user.organization_id


# -------------------------------------------------------
# LOOKUP — open (auth only)
# -------------------------------------------------------
@router.get("/lookup")
def lookup_clients(
    db: Session = Depends(deps.get_db),
    current_user: Union[Organization, Employee] = Depends(deps.get_current_user),
    search: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=200)
):
    """Lightweight lookup for dropdowns. No RBAC required."""
    query = db.query(ProjectClient).filter(
        ProjectClient.organization_id == _org_id(current_user),
        ProjectClient.is_active == True,
        ProjectClient.is_deleted == False
    )
    if search:
        query = query.filter(ProjectClient.client_name.ilike(f"%{search}%"))
    clients = query.order_by(ProjectClient.client_name).limit(limit).all()
    return {
        "success": True,
        "data": [{"uuid": c.uuid, "client_name": c.client_name, "client_code": c.client_code, "is_internal": c.is_internal} for c in clients]
    }


# -------------------------------------------------------
# LIST — Permission 79
# -------------------------------------------------------
@router.get("/", response_model=ProjectClientListResponse)
def list_clients(
    db: Session = Depends(deps.get_db),
    current_user: Union[Organization, Employee] = Depends(deps.get_current_user),
    search: Optional[str] = Query(None),
    is_active: Optional[bool] = Query(None),
    is_internal: Optional[bool] = Query(None),
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    sort_by: Optional[str] = Query("created_at"),
    sort_order: Optional[str] = Query("desc")
):
    _require(db, current_user, "79", "list")
    org_id = _org_id(current_user)

    query = db.query(ProjectClient).filter(
        ProjectClient.organization_id == org_id,
        ProjectClient.is_deleted == False
    )
    if search:
        query = query.filter(ProjectClient.client_name.ilike(f"%{search}%"))
    if is_active is not None:
        query = query.filter(ProjectClient.is_active == is_active)
    if is_internal is not None:
        query = query.filter(ProjectClient.is_internal == is_internal)

    # Sorting logic
    sort_column = getattr(ProjectClient, sort_by, ProjectClient.created_at) if sort_by in ["client_code", "client_name", "contact_person", "is_active", "created_at"] else ProjectClient.created_at
    if sort_order == "desc":
        query = query.order_by(sort_column.desc())
    else:
        query = query.order_by(sort_column.asc())

    total = query.count()
    clients = query.offset((page - 1) * limit).limit(limit).all()

    return ProjectClientListResponse(
        success=True, message="Clients retrieved successfully",
        data=[ProjectClientSchema.model_validate(c) for c in clients],
        pagination={"total_records": total, "current_page": page, "total_pages": (total + limit - 1) // limit, "page_size": limit}
    )


# -------------------------------------------------------
# GET DETAIL — Permission 79
# -------------------------------------------------------
@router.get("/{client_uuid}", response_model=ProjectClientResponse)
def get_client(
    client_uuid: uuid.UUID,
    db: Session = Depends(deps.get_db),
    current_user: Union[Organization, Employee] = Depends(deps.get_current_user)
):
    _require(db, current_user, "79", "view")
    client = db.query(ProjectClient).filter(
        ProjectClient.uuid == client_uuid,
        ProjectClient.organization_id == _org_id(current_user),
        ProjectClient.is_deleted == False
    ).first()
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")
    return ProjectClientResponse(success=True, message="Client retrieved", data=ProjectClientSchema.model_validate(client))


# -------------------------------------------------------
# CREATE — Permission 80
# -------------------------------------------------------
@router.post("/", response_model=ProjectClientResponse, status_code=status.HTTP_201_CREATED)
def create_client(
    client_in: ProjectClientCreate,
    db: Session = Depends(deps.get_db),
    current_user: Union[Organization, Employee] = Depends(deps.get_current_user)
):
    _require(db, current_user, "80", "create")
    org_id = _org_id(current_user)

    if db.query(ProjectClient).filter(
        ProjectClient.organization_id == org_id,
        ProjectClient.client_code == client_in.client_code,
        ProjectClient.is_deleted == False
    ).first():
        raise HTTPException(status_code=400, detail=f"Client code '{client_in.client_code}' already exists")

    employee_id = current_user.id if isinstance(current_user, Employee) else None
    client = ProjectClient(organization_id=org_id, created_by=employee_id, **client_in.model_dump())
    db.add(client)
    db.commit()
    db.refresh(client)
    return ProjectClientResponse(success=True, message="Client created successfully", data=ProjectClientSchema.model_validate(client))


# -------------------------------------------------------
# UPDATE — Permission 81
# -------------------------------------------------------
@router.put("/{client_uuid}", response_model=ProjectClientResponse)
def update_client(
    client_uuid: uuid.UUID,
    client_in: ProjectClientUpdate,
    db: Session = Depends(deps.get_db),
    current_user: Union[Organization, Employee] = Depends(deps.get_current_user)
):
    _require(db, current_user, "81", "update")
    client = db.query(ProjectClient).filter(
        ProjectClient.uuid == client_uuid,
        ProjectClient.organization_id == _org_id(current_user),
        ProjectClient.is_deleted == False
    ).first()
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")

    for field, value in client_in.model_dump(exclude_unset=True).items():
        setattr(client, field, value)
    db.commit()
    db.refresh(client)
    return ProjectClientResponse(success=True, message="Client updated successfully", data=ProjectClientSchema.model_validate(client))


# -------------------------------------------------------
# DELETE — Permission 82
# -------------------------------------------------------
@router.delete("/{client_uuid}")
def delete_client(
    client_uuid: uuid.UUID,
    db: Session = Depends(deps.get_db),
    current_user: Union[Organization, Employee] = Depends(deps.get_current_user)
):
    _require(db, current_user, "82", "delete")
    client = db.query(ProjectClient).filter(
        ProjectClient.uuid == client_uuid,
        ProjectClient.organization_id == _org_id(current_user),
        ProjectClient.is_deleted == False
    ).first()
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")

    client.is_deleted = True
    client.deleted_at = datetime.utcnow()
    client.is_active = False
    db.commit()
    return {"success": True, "message": "Client deleted successfully"}
