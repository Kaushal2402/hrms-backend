import uuid
from decimal import Decimal
from typing import List, Optional, Union
from fastapi import APIRouter, Depends, HTTPException, Query, status, Request
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.api import deps
from app.utils.payroll_audit import PayrollAuditService
from app.models.organization import Organization
from app.models.employee import Employee, Department, Location
from app.models.payroll import SalaryTemplate, SalaryTemplateComponent, SalaryComponent, EmployeeSalary
from app.schemas.payroll_salary_templates import (
    SalaryTemplateCreate, SalaryTemplateUpdate, SalaryTemplateSchema, SalaryTemplateDetailedSchema,
    SalaryTemplateResponse, SalaryTemplateDetailedResponse, SalaryTemplateListResponse, SalaryTemplateClone,
    SalaryTemplateComponentUpdate, PreviewRequest, SalaryTemplateLookResponse
)
from app.core.permissions import PayrollSalaryComponentPermissions

router = APIRouter()

def _get_org_id(current_user: Union[Organization, Employee]) -> int:
    return current_user.id if isinstance(current_user, Organization) else current_user.organization_id

def _require_permission(db, current_user, code, action_label):
    if isinstance(current_user, Organization): return
    if not deps.has_permission(db, current_user, code):
        raise HTTPException(status_code=403, detail=f"Permission denied: {action_label}")

def _uuids_to_ids(db: Session, model, uuids: List[uuid.UUID], org_id: int) -> List[int]:
    if not uuids: return []
    return [r.id for r in db.query(model.id).filter(model.uuid.in_(uuids), model.organization_id == org_id).all()]

def _enrich_template(db: Session, template: SalaryTemplate):
    """Enrich template with related objects for response."""
    # Convert ORM to dict to add extra fields for Pydantic
    data = {c.name: getattr(template, c.name) for c in template.__table__.columns}
    data['uuid'] = template.uuid
    
    if template.department_ids:
        data['departments'] = db.query(Department).filter(Department.id.in_(template.department_ids)).all()
    else:
        data['departments'] = []
        
    if template.location_ids:
        data['locations'] = db.query(Location).filter(Location.id.in_(template.location_ids)).all()
    else:
        data['locations'] = []
    
    # Also handle components if it's a detailed schema
    if hasattr(template, 'components'):
        data['components'] = []
        for tc in template.components:
            # Map ORM to dict
            comp_dict = {c.name: getattr(tc, c.name) for c in tc.__table__.columns}
            
            # Fetch component_uuid from the master SalaryComponent
            salary_comp = db.query(SalaryComponent.uuid).filter(SalaryComponent.id == tc.component_id).first()
            comp_dict['component_uuid'] = salary_comp[0] if salary_comp else None
            
            data['components'].append(comp_dict)
        
    return data

@router.get("/", response_model=SalaryTemplateListResponse)
def get_templates(
    page: int = Query(1, ge=1),
    limit: int = Query(10, ge=1, le=100),
    search: Optional[str] = Query(None),
    is_active: Optional[bool] = Query(None),
    applicable_to: Optional[str] = Query(None),
    sort_by: str = Query("template_name"),
    sort_order: str = Query("asc"),
    db: Session = Depends(deps.get_db),
    current_user: Union[Organization, Employee] = Depends(deps.get_current_user)
):
    _require_permission(db, current_user, PayrollSalaryComponentPermissions.READ, "list salary templates")
    org_id = _get_org_id(current_user)
    query = db.query(SalaryTemplate).filter(SalaryTemplate.organization_id == org_id)
    
    if search:
        search_filter = f"%{search}%"
        query = query.filter(
            (SalaryTemplate.template_name.ilike(search_filter)) |
            (SalaryTemplate.template_code.ilike(search_filter))
        )
    
    if is_active is not None: query = query.filter(SalaryTemplate.is_active == is_active)
    if applicable_to: query = query.filter(SalaryTemplate.applicable_to == applicable_to)
    
    # Sorting
    if sort_by and hasattr(SalaryTemplate, sort_by):
        column = getattr(SalaryTemplate, sort_by)
        if sort_order.lower() == "desc":
            query = query.order_by(column.desc())
        else:
            query = query.order_by(column.asc())
    else:
        query = query.order_by(SalaryTemplate.template_name.asc())
    
    total_records = query.count()
    items = query.offset((page - 1) * limit).limit(limit).all()
    enriched_items = [_enrich_template(db, item) for item in items]
    return SalaryTemplateListResponse(
        success=True, 
        message="Salary templates retrieved successfully.", 
        data=enriched_items, 
        pagination={'total_records': total_records, 'current_page': page, 'total_pages': (total_records + limit - 1) // limit, 'page_size': limit}
    )

@router.get("/lookup", response_model=SalaryTemplateLookResponse)
def lookup_templates(
    page: int = Query(1, ge=1),
    limit: int = Query(50, ge=1, le=100),
    search: Optional[str] = Query(None),
    is_active: Optional[bool] = Query(True),
    db: Session = Depends(deps.get_db),
    current_user: Union[Organization, Employee] = Depends(deps.get_current_user)
):
    # NO RBAC CHECK - Used for cross-module selection
    org_id = _get_org_id(current_user)
    query = db.query(SalaryTemplate).filter(SalaryTemplate.organization_id == org_id)
    
    if search:
        search_filter = f"%{search}%"
        query = query.filter(
            (SalaryTemplate.template_name.ilike(search_filter)) |
            (SalaryTemplate.template_code.ilike(search_filter))
        )

    if is_active is not None: query = query.filter(SalaryTemplate.is_active == is_active)
    
    total = query.count()
    items = query.with_entities(SalaryTemplate.uuid, SalaryTemplate.template_name, SalaryTemplate.template_code).offset((page - 1) * limit).limit(limit).all()
    
    # Map to dict for response
    data = [{"uuid": i.uuid, "template_name": i.template_name, "template_code": i.template_code} for i in items]
    
    return SalaryTemplateLookResponse(
        success=True,
        message="Salary templates lookup retrieved successfully.",
        data=data,
        pagination={'total_records': total, 'current_page': page, 'total_pages': (total + limit - 1) // limit, 'page_size': limit}
    )

@router.post("/", response_model=SalaryTemplateResponse)
def create_template(
    item_in: SalaryTemplateCreate,
    request: Request,
    db: Session = Depends(deps.get_db),
    current_user: Union[Organization, Employee] = Depends(deps.get_current_user)
):
    _require_permission(db, current_user, PayrollSalaryComponentPermissions.CREATE, "create salary template")
    org_id = _get_org_id(current_user)
    if db.query(SalaryTemplate).filter(SalaryTemplate.organization_id == org_id, SalaryTemplate.template_code == item_in.template_code).first():
        raise HTTPException(400, "Code exists")
    
    if item_in.is_default:
        db.query(SalaryTemplate).filter(SalaryTemplate.organization_id == org_id).update({"is_default": False})
    
    # Map UUIDs to IDs
    dept_ids = _uuids_to_ids(db, Department, item_in.department_uuids, org_id) if item_in.department_uuids else []
    loc_ids = _uuids_to_ids(db, Location, item_in.location_uuids, org_id) if item_in.location_uuids else []
    
    template_data = item_in.model_dump(exclude={'components', 'department_uuids', 'location_uuids', 'grade_uuids'})
    template_data['department_ids'] = dept_ids
    template_data['location_ids'] = loc_ids
    
    template = SalaryTemplate(organization_id=org_id, **template_data)
    db.add(template)
    db.flush()  # Get template ID
    
    # Add components
    if item_in.components:
        for comp_in in item_in.components:
            comp_master = db.query(SalaryComponent).filter(SalaryComponent.uuid == comp_in.component_uuid, SalaryComponent.organization_id == org_id).first()
            if not comp_master:
                continue
            
            tmpl_comp = SalaryTemplateComponent(
                template_id=template.id,
                component_id=comp_master.id,
                **comp_in.model_dump(exclude={'component_uuid'})
            )
            db.add(tmpl_comp)
    
    db.commit()
    db.refresh(template)
    
    # Audit Log
    PayrollAuditService.log(
        db=db,
        current_user=current_user,
        action_type="template_created",
        entity_type="salary_template",
        entity_id=template.id,
        after_state=PayrollAuditService.get_model_dict(template),
        change_summary=f"Created salary template: {template.template_name}",
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent")
    )
    db.commit()
    
    return SalaryTemplateResponse(success=True, message="Salary template created successfully.", data=_enrich_template(db, template))

@router.get("/{template_uuid}", response_model=SalaryTemplateDetailedResponse)
def get_template(template_uuid: uuid.UUID, db: Session = Depends(deps.get_db), current_user: Union[Organization, Employee] = Depends(deps.get_current_user)):
    _require_permission(db, current_user, PayrollSalaryComponentPermissions.READ, "view salary template")
    item = db.query(SalaryTemplate).filter(SalaryTemplate.uuid == template_uuid, SalaryTemplate.organization_id == _get_org_id(current_user)).first()
    if not item: raise HTTPException(404, "Not found")
    return SalaryTemplateDetailedResponse(success=True, message="Salary template details retrieved successfully.", data=_enrich_template(db, item))

@router.put("/{template_uuid}", response_model=SalaryTemplateResponse)
def update_template(
    template_uuid: uuid.UUID, 
    item_in: SalaryTemplateUpdate, 
    request: Request,
    db: Session = Depends(deps.get_db), 
    current_user: Union[Organization, Employee] = Depends(deps.get_current_user)
):
    _require_permission(db, current_user, PayrollSalaryComponentPermissions.UPDATE, "update salary template")
    org_id = _get_org_id(current_user)
    item = db.query(SalaryTemplate).filter(SalaryTemplate.uuid == template_uuid, SalaryTemplate.organization_id == org_id).first()
    if not item: raise HTTPException(404, "Not found")
    if item_in.is_default: db.query(SalaryTemplate).filter(SalaryTemplate.organization_id == org_id).update({"is_default": False})
    
    # Capture state before update
    before_state = PayrollAuditService.get_model_dict(item)
    
    # Map UUIDs to IDs if provided
    update_data = item_in.model_dump(exclude_unset=True, exclude={'components', 'department_uuids', 'location_uuids', 'grade_uuids'})
    if item_in.department_uuids is not None:
        update_data['department_ids'] = _uuids_to_ids(db, Department, item_in.department_uuids, org_id)
    if item_in.location_uuids is not None:
        update_data['location_ids'] = _uuids_to_ids(db, Location, item_in.location_uuids, org_id)
        
    for f, v in update_data.items(): setattr(item, f, v)
    
    # Handle components synchronization
    if item_in.components is not None:
        # Simple approach: clear and recreate
        db.query(SalaryTemplateComponent).filter(SalaryTemplateComponent.template_id == item.id).delete()
        for comp_in in item_in.components:
            comp_master = db.query(SalaryComponent).filter(SalaryComponent.uuid == comp_in.component_uuid, SalaryComponent.organization_id == org_id).first()
            if not comp_master:
                continue
            
            tmpl_comp = SalaryTemplateComponent(
                template_id=item.id,
                component_id=comp_master.id,
                **comp_in.model_dump(exclude={'component_uuid'})
            )
            db.add(tmpl_comp)
            
    db.commit()
    db.refresh(item)
    
    # Audit Log
    PayrollAuditService.log(
        db=db,
        current_user=current_user,
        action_type="template_updated",
        entity_type="salary_template",
        entity_id=item.id,
        before_state=before_state,
        after_state=PayrollAuditService.get_model_dict(item),
        change_summary=f"Updated salary template: {item.template_name}",
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent")
    )
    db.commit()
    
    return SalaryTemplateResponse(success=True, message="Salary template updated successfully.", data=_enrich_template(db, item))

@router.delete("/{template_uuid}")
def delete_template(
    template_uuid: uuid.UUID, 
    request: Request,
    db: Session = Depends(deps.get_db), 
    current_user: Union[Organization, Employee] = Depends(deps.get_current_user)
):
    _require_permission(db, current_user, PayrollSalaryComponentPermissions.DELETE, "delete salary template")
    item = db.query(SalaryTemplate).filter(SalaryTemplate.uuid == template_uuid, SalaryTemplate.organization_id == _get_org_id(current_user)).first()
    if not item: raise HTTPException(404, "Not found")
    if db.query(EmployeeSalary).filter(EmployeeSalary.template_id == item.id).first(): raise HTTPException(400, "In use")
    
    before_state = PayrollAuditService.get_model_dict(item)
    db.delete(item)
    
    # Audit Log
    PayrollAuditService.log(
        db=db,
        current_user=current_user,
        action_type="template_deleted",
        entity_type="salary_template",
        entity_id=item.id,
        before_state=before_state,
        change_summary=f"Deleted salary template: {item.template_name}",
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent")
    )
    db.commit()
    
    return {"success": True, "message": "Salary template deleted successfully."}

@router.post("/{template_uuid}/clone", response_model=SalaryTemplateResponse)
def clone_template(
    template_uuid: uuid.UUID, 
    clone_in: SalaryTemplateClone, 
    request: Request,
    db: Session = Depends(deps.get_db), 
    current_user: Union[Organization, Employee] = Depends(deps.get_current_user)
):
    _require_permission(db, current_user, PayrollSalaryComponentPermissions.CREATE, "clone salary template")
    org_id = _get_org_id(current_user)
    source = db.query(SalaryTemplate).filter(SalaryTemplate.uuid == template_uuid, SalaryTemplate.organization_id == org_id).first()
    if not source: raise HTTPException(404, "Source not found")
    
    # Check if new code exists
    if db.query(SalaryTemplate).filter(SalaryTemplate.organization_id == org_id, SalaryTemplate.template_code == clone_in.new_template_code).first():
        raise HTTPException(400, f"Salary template with code '{clone_in.new_template_code}' already exists.")
    
    # Extract attributes and exclude internal/unique/audit fields
    exclude_fields = {'id', 'uuid', 'organization_id', 'template_name', 'template_code', 'created_at', 'updated_at', '_sa_instance_state'}
    data = {k: v for k, v in source.__dict__.items() if k not in exclude_fields}
    
    new_template = SalaryTemplate(
        organization_id=org_id, 
        template_name=clone_in.new_template_name, 
        template_code=clone_in.new_template_code, 
        **data
    )
    db.add(new_template)
    db.flush() # Get new ID
    
    # Clone components
    source_components = db.query(SalaryTemplateComponent).filter(SalaryTemplateComponent.template_id == source.id).all()
    for sc in source_components:
        new_sc = SalaryTemplateComponent(
            template_id=new_template.id,
            component_id=sc.component_id,
            calculation_type_override=sc.calculation_type_override,
            calculation_value_override=sc.calculation_value_override,
            formula_override=sc.formula_override,
            min_value=sc.min_value,
            max_value=sc.max_value,
            display_order=sc.display_order,
            is_mandatory=sc.is_mandatory,
            is_active=sc.is_active
        )
        db.add(new_sc)
        
    db.commit()
    db.refresh(new_template)
    
    # Audit Log
    PayrollAuditService.log(
        db=db,
        current_user=current_user,
        action_type="template_cloned",
        entity_type="salary_template",
        entity_id=new_template.id,
        after_state=PayrollAuditService.get_model_dict(new_template),
        change_summary=f"Cloned salary template from {source.template_name} to {new_template.template_name}",
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent")
    )
    db.commit()
    
    return SalaryTemplateResponse(success=True, message="Salary template cloned successfully.", data=_enrich_template(db, new_template))

@router.post("/preview", response_model=dict)
def preview_salary(
    preview_in: PreviewRequest,
    template_uuid: Optional[uuid.UUID] = None,
    db: Session = Depends(deps.get_db),
    current_user: Union[Organization, Employee] = Depends(deps.get_current_user)
):
    """Simple preview logic for salary calculation based on template"""
    # This is a placeholder for actual complex calculation logic
    annual_ctc = preview_in.annual_ctc
    monthly_ctc = annual_ctc / 12
    
    # In a real scenario, we'd fetch the template and calculate all components
    # For now, return a basic structure
    return {
        "success": True,
        "data": {
            "annual_ctc": float(annual_ctc),
            "monthly_ctc": float(monthly_ctc),
            "components": [] # To be implemented with actual calculation engine
        }
    }

@router.post("/{template_uuid}/components", response_model=SalaryTemplateResponse)
def update_components(
    template_uuid: uuid.UUID, 
    comp_in: SalaryTemplateComponentUpdate, 
    request: Request,
    db: Session = Depends(deps.get_db), 
    current_user: Union[Organization, Employee] = Depends(deps.get_current_user)
):
    _require_permission(db, current_user, PayrollSalaryComponentPermissions.UPDATE, "update salary template components")
    org_id = _get_org_id(current_user)
    template = db.query(SalaryTemplate).filter(SalaryTemplate.uuid == template_uuid, SalaryTemplate.organization_id == org_id).first()
    if not template: raise HTTPException(404, "Template not found")
    
    # Capture state before update
    before_state = PayrollAuditService.get_model_dict(template)
    
    # Remove existing components
    db.query(SalaryTemplateComponent).filter(SalaryTemplateComponent.template_id == template.id).delete()
    
    # Add new components
    for comp in comp_in.components:
        salary_comp = db.query(SalaryComponent).filter(SalaryComponent.uuid == comp.component_uuid, SalaryComponent.organization_id == org_id).first()
        if not salary_comp: continue
        
        new_comp = SalaryTemplateComponent(
            template_id=template.id,
            component_id=salary_comp.id,
            calculation_type_override=comp.calculation_type_override,
            calculation_value_override=comp.calculation_value_override,
            formula_override=comp.formula_override,
            min_value=comp.min_value,
            max_value=comp.max_value,
            display_order=comp.display_order,
            is_mandatory=comp.is_mandatory
        )
        db.add(new_comp)
    
    db.commit()
    db.refresh(template)
    
    # Audit Log
    PayrollAuditService.log(
        db=db,
        current_user=current_user,
        action_type="template_components_updated",
        entity_type="salary_template",
        entity_id=template.id,
        before_state=before_state,
        change_summary=f"Updated components for salary template: {template.template_name}",
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent")
    )
    db.commit()
    
    return SalaryTemplateResponse(success=True, message="Salary template components updated successfully.", data=_enrich_template(db, template))

@router.get("/{template_uuid}/preview")
def preview_template(template_uuid: uuid.UUID, annual_ctc: Decimal = Query(...), db: Session = Depends(deps.get_db), current_user: Union[Organization, Employee] = Depends(deps.get_current_user)):
    _require_permission(db, current_user, PayrollSalaryComponentPermissions.READ, "preview salary template")
    org_id = _get_org_id(current_user)
    template = db.query(SalaryTemplate).filter(SalaryTemplate.uuid == template_uuid, SalaryTemplate.organization_id == org_id).first()
    if not template: raise HTTPException(404, "Template not found")
    
    # Fetch components in order
    template_components = db.query(SalaryTemplateComponent).filter(
        SalaryTemplateComponent.template_id == template.id,
        SalaryTemplateComponent.is_active == True
    ).order_by(SalaryTemplateComponent.display_order.asc()).all()
    
    monthly_ctc = annual_ctc / 12
    breakdown = []
    
    # Simple calculation engine
    # In production, this would be a more complex engine handling formulas and dependencies
    for tc in template_components:
        comp_master = db.query(SalaryComponent).filter(SalaryComponent.id == tc.component_id).first()
        if not comp_master: continue
        
        calc_type = tc.calculation_type_override or comp_master.calculation_type
        calc_value = tc.calculation_value_override or comp_master.calculation_value or 0
        
        amount = Decimal(0)
        if calc_type == "fixed":
            amount = calc_value
        elif calc_type == "percentage":
            # For preview, if based_on is not defined or empty, we assume percentage of CTC
            # In a real engine, we would handle specific "based_on" logic
            amount = (calc_value / 100) * monthly_ctc
        
        # Apply min/max limits if defined
        if tc.min_value is not None:
            amount = max(amount, tc.min_value)
        if tc.max_value is not None:
            amount = min(amount, tc.max_value)
            
        breakdown.append({
            "component_uuid": comp_master.uuid,
            "component_name": comp_master.component_name,
            "component_code": comp_master.component_code,
            "component_type": comp_master.component_type,
            "amount": float(round(amount, 2)),
            "is_taxable": comp_master.is_taxable,
            "show_on_payslip": comp_master.show_on_payslip
        })
    
    return {
        "success": True,
        "data": {
            "template_name": template.template_name,
            "annual_ctc": float(annual_ctc),
            "monthly_ctc": float(round(monthly_ctc, 2)),
            "breakdown": breakdown
        }
    }