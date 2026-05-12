import uuid
from typing import List, Optional, Union
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from sqlalchemy import or_

from app.api import deps
from app.models.organization import Organization
from app.models.employee import Employee
from app.models.payroll import SalaryComponent, SalaryTemplateComponent, SalaryTemplate
from app.core.permissions import PayrollSalaryComponentPermissions
from app.schemas.payroll_salary_components import (
    SalaryComponentCreate,
    SalaryComponentUpdate,
    SalaryComponentSchema,
    SalaryComponentResponse,
    SalaryComponentListResponse
)

router = APIRouter()

def _get_org_id(current_user: Union[Organization, Employee]) -> int:
    if isinstance(current_user, Organization):
        return current_user.id
    return current_user.organization_id

def _require_permission(db, current_user, code, action_label):
    if isinstance(current_user, Organization):
        return
    if not deps.has_permission(db, current_user, code):
        raise HTTPException(status_code=403, detail=f"You do not have permission to {action_label} (requires code: {code})")

@router.get("/", response_model=SalaryComponentListResponse)
def get_salary_components(
    page: int = Query(1, ge=1),
    limit: int = Query(10, ge=1, le=100),
    search: Optional[str] = Query(None),
    component_type: Optional[str] = Query(None),
    is_active: Optional[bool] = Query(None),
    sort_by: Optional[str] = Query("component_name"),
    sort_order: Optional[str] = Query("asc"),
    db: Session = Depends(deps.get_db),
    current_user: Union[Organization, Employee] = Depends(deps.get_current_user),
    current_org: Organization = Depends(deps.get_current_org)
):
    _require_permission(db, current_user, PayrollSalaryComponentPermissions.READ, "list salary components")
    
    query = db.query(SalaryComponent).filter(SalaryComponent.organization_id == current_org.id)
    
    if component_type:
        query = query.filter(SalaryComponent.component_type == component_type)
    if is_active is not None:
        query = query.filter(SalaryComponent.is_active == is_active)
    if search:
        search_term = f"%{search}%"
        query = query.filter(or_(SalaryComponent.component_name.ilike(search_term), SalaryComponent.component_code.ilike(search_term)))
        
    # Sorting
    if sort_by and hasattr(SalaryComponent, sort_by):
        col = getattr(SalaryComponent, sort_by)
        if sort_order == "desc":
            query = query.order_by(col.desc())
        else:
            query = query.order_by(col.asc())
    else:
        query = query.order_by(SalaryComponent.component_name.asc())
        
    total_records = query.count()
    total_pages = (total_records + limit - 1) // limit if total_records > 0 else 0
    items = query.offset((page - 1) * limit).limit(limit).all()
    
    return SalaryComponentListResponse(
        success=True, message="Salary components retrieved successfully",
        data=[SalaryComponentSchema.model_validate(i) for i in items],
        pagination={'total_records': total_records, 'current_page': page, 'total_pages': total_pages, 'page_size': limit}
    )

@router.post("/", response_model=SalaryComponentResponse)
def create_salary_component(
    item_in: SalaryComponentCreate,
    db: Session = Depends(deps.get_db),
    current_user: Union[Organization, Employee] = Depends(deps.get_current_user),
    current_org: Organization = Depends(deps.get_current_org)
):
    _require_permission(db, current_user, PayrollSalaryComponentPermissions.CREATE, "create salary component")
    org_id = _get_org_id(current_user)
    
    if db.query(SalaryComponent).filter(SalaryComponent.organization_id == org_id, SalaryComponent.component_code == item_in.component_code).first():
        raise HTTPException(400, "Component code already exists")
        
    item = SalaryComponent(organization_id=org_id, **item_in.model_dump())
    db.add(item)
    db.commit()
    db.refresh(item)
    return {"success": True, "message": "Salary component created successfully", "data": SalaryComponentSchema.model_validate(item)}

@router.get("/{component_uuid}", response_model=SalaryComponentResponse)
def get_salary_component(
    component_uuid: uuid.UUID,
    db: Session = Depends(deps.get_db),
    current_user: Union[Organization, Employee] = Depends(deps.get_current_user),
    current_org: Organization = Depends(deps.get_current_org)
):
    _require_permission(db, current_user, PayrollSalaryComponentPermissions.READ, "view salary component")
    item = db.query(SalaryComponent).filter(SalaryComponent.uuid == component_uuid, SalaryComponent.organization_id == current_org.id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Salary component not found")
    return {"success": True, "message": "Salary component retrieved successfully", "data": SalaryComponentSchema.model_validate(item)}

@router.put("/{component_uuid}", response_model=SalaryComponentResponse)
def update_salary_component(
    component_uuid: uuid.UUID,
    item_in: SalaryComponentUpdate,
    db: Session = Depends(deps.get_db),
    current_user: Union[Organization, Employee] = Depends(deps.get_current_user),
    current_org: Organization = Depends(deps.get_current_org)
):
    _require_permission(db, current_user, PayrollSalaryComponentPermissions.UPDATE, "update salary component")
    item = db.query(SalaryComponent).filter(SalaryComponent.uuid == component_uuid, SalaryComponent.organization_id == current_org.id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Salary component not found")
        
    if item_in.component_code and item_in.component_code != item.component_code:
        if db.query(SalaryTemplateComponent).filter(SalaryTemplateComponent.component_id == item.id).first():
            raise HTTPException(400, "Cannot change code of component used in templates")
            
    for field, value in item_in.model_dump(exclude_unset=True).items():
        setattr(item, field, value)
    db.commit()
    db.refresh(item)
    return {"success": True, "message": "Salary component updated successfully", "data": SalaryComponentSchema.model_validate(item)}

@router.delete("/{component_uuid}")
def delete_salary_component(
    component_uuid: uuid.UUID,
    db: Session = Depends(deps.get_db),
    current_user: Union[Organization, Employee] = Depends(deps.get_current_user),
    current_org: Organization = Depends(deps.get_current_org)
):
    _require_permission(db, current_user, PayrollSalaryComponentPermissions.DELETE, "delete salary component")
    item = db.query(SalaryComponent).filter(SalaryComponent.uuid == component_uuid, SalaryComponent.organization_id == current_org.id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Salary component not found")
        
    # Check if component is used in any active template (join to SalaryTemplate for is_active check)
    in_active_template = (
        db.query(SalaryTemplateComponent)
        .join(SalaryTemplate, SalaryTemplateComponent.template_id == SalaryTemplate.id)
        .filter(
            SalaryTemplateComponent.component_id == item.id,
            SalaryTemplateComponent.is_active == True,
            SalaryTemplate.is_active == True
        )
        .first()
    )
    if in_active_template:
        raise HTTPException(400, "Cannot deactivate component used in active templates")
        
    item.is_active = False
    db.commit()
    return {"success": True, "message": "Salary component deactivated successfully"}