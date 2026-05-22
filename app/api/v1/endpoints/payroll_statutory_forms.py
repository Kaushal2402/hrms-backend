import uuid
import io
from typing import List, Optional, Union
from datetime import datetime, date
from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from sqlalchemy import func, desc, or_

from app.api import deps
from app.models.organization import Organization
from app.models.employee import Employee
from app.models.payroll import StatutoryForm
from app.schemas.payroll_statutory_forms import (
    StatutoryFormSchema, StatutoryFormResponse, StatutoryFormListResponse,
    StatutoryFormCreate, StatutoryFormFilingPayload, Form16BulkGeneratePayload
)
from app.core.permissions import PayrollStatutoryFormPermissions

router = APIRouter()
employee_router = APIRouter()

def _get_org_id(current_user: Union[Organization, Employee]) -> int:
    return current_user.id if isinstance(current_user, Organization) else current_user.organization_id

def _require_permission(db: Session, current_user: Union[Organization, Employee], code: str, action: str):
    if not isinstance(current_user, Organization) and not deps.has_permission(db, current_user, code):
        raise HTTPException(status_code=403, detail=f"Permission denied: {action}")

def _get_form_by_id_or_uuid(db: Session, form_id: str, org_id: int):
    try:
        val = uuid.UUID(str(form_id))
        return db.query(StatutoryForm).filter(
            StatutoryForm.uuid == val,
            StatutoryForm.organization_id == org_id
        ).first()
    except ValueError:
        try:
            int_id = int(form_id)
            return db.query(StatutoryForm).filter(
                StatutoryForm.id == int_id,
                StatutoryForm.organization_id == org_id
            ).first()
        except ValueError:
            return None

@router.get("/", response_model=StatutoryFormListResponse)
def get_statutory_forms(
    page: int = Query(1, ge=1),
    limit: int = Query(10, ge=1, le=100),
    form_type: Optional[str] = None,
    financial_year: Optional[str] = None,
    filing_status: Optional[str] = None,
    db: Session = Depends(deps.get_db),
    current_user: Union[Organization, Employee] = Depends(deps.get_current_user)
):
    _require_permission(db, current_user, PayrollStatutoryFormPermissions.READ, "list")
    org_id = _get_org_id(current_user)
    
    query = db.query(StatutoryForm).filter(StatutoryForm.organization_id == org_id)
    
    if form_type:
        query = query.filter(StatutoryForm.form_type == form_type)
    if financial_year:
        query = query.filter(StatutoryForm.financial_year == financial_year)
    if filing_status:
        query = query.filter(StatutoryForm.filing_status == filing_status)
        
    query = query.order_by(desc(StatutoryForm.created_at))
    
    total = query.count()
    items = query.offset((page - 1) * limit).limit(limit).all()
    
    return StatutoryFormListResponse(
        success=True,
        message="Statutory forms retrieved successfully",
        data=items,
        pagination={
            "total_records": total,
            "current_page": page,
            "total_pages": (total + limit - 1) // limit,
            "page_size": limit
        }
    )

@router.post("/generate", response_model=StatutoryFormResponse)
def generate_statutory_form(
    data: StatutoryFormCreate,
    db: Session = Depends(deps.get_db),
    current_user: Union[Organization, Employee] = Depends(deps.get_current_user)
):
    _require_permission(db, current_user, PayrollStatutoryFormPermissions.CREATE, "generate")
    org_id = _get_org_id(current_user)
    
    # Generate unique form number
    form_type_str = data.form_type.upper().replace('_', '')
    unique_suffix = uuid.uuid4().hex[:6].upper()
    form_number = f"SF-{form_type_str}-{data.financial_year.replace('-', '')}-{unique_suffix}"
    
    form_name = f"Statutory {data.form_type.replace('_', ' ').title()} - {data.financial_year}"
    if data.period:
        form_name += f" ({data.period})"
        
    new_form = StatutoryForm(
        organization_id=org_id,
        form_type=data.form_type,
        form_name=form_name,
        form_number=form_number,
        financial_year=data.financial_year,
        period=data.period,
        filing_status="pending",
        amount=data.amount,
        notes=data.notes,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
        created_by=None if isinstance(current_user, Organization) else current_user.id
    )
    db.add(new_form)
    db.commit()
    db.refresh(new_form)
    
    return StatutoryFormResponse(
        success=True,
        message="Statutory form generated successfully",
        data=new_form
    )

@router.get("/{form_id}", response_model=StatutoryFormResponse)
def get_statutory_form_details(
    form_id: str,
    db: Session = Depends(deps.get_db),
    current_user: Union[Organization, Employee] = Depends(deps.get_current_user)
):
    _require_permission(db, current_user, PayrollStatutoryFormPermissions.READ, "detail")
    org_id = _get_org_id(current_user)
    
    form = _get_form_by_id_or_uuid(db, form_id, org_id)
    if not form:
        raise HTTPException(status_code=404, detail="Statutory form not found")
        
    return StatutoryFormResponse(
        success=True,
        message="Statutory form details retrieved successfully",
        data=form
    )

@router.get("/{form_id}/download")
def download_statutory_form(
    form_id: str,
    db: Session = Depends(deps.get_db),
    current_user: Union[Organization, Employee] = Depends(deps.get_current_user)
):
    _require_permission(db, current_user, PayrollStatutoryFormPermissions.READ, "download")
    org_id = _get_org_id(current_user)
    
    form = _get_form_by_id_or_uuid(db, form_id, org_id)
    if not form:
        raise HTTPException(status_code=404, detail="Statutory form not found")
        
    # Generate mock PDF bytes
    pdf_buffer = io.BytesIO()
    pdf_buffer.write(b"%PDF-1.4\n")
    pdf_buffer.write(f"1 0 obj\n<< /Title (Statutory Form {form.form_name}) /Author (HRMS) >>\nendobj\n".encode())
    pdf_buffer.write(b"xref\n0 1\n0000000000 65535 f\ntrailer\n<< /Size 2 /Root 1 0 R >>\nstartxref\n120\n%%EOF\n")
    pdf_buffer.seek(0)
    
    safe_filename = f"statutory_form_{form.form_type}_{form.financial_year}.pdf"
    
    return StreamingResponse(
        pdf_buffer,
        media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename={safe_filename}"}
    )

@router.post("/{form_id}/file", response_model=StatutoryFormResponse)
def file_statutory_form(
    form_id: str,
    payload: StatutoryFormFilingPayload,
    db: Session = Depends(deps.get_db),
    current_user: Union[Organization, Employee] = Depends(deps.get_current_user)
):
    _require_permission(db, current_user, PayrollStatutoryFormPermissions.CREATE, "file")
    org_id = _get_org_id(current_user)
    
    form = _get_form_by_id_or_uuid(db, form_id, org_id)
    if not form:
        raise HTTPException(status_code=404, detail="Statutory form not found")
        
    form.filing_status = "filed"
    form.filed_at = datetime.utcnow()
    form.filing_reference = payload.filing_reference
    form.acknowledgment_number = payload.acknowledgment_number
    if payload.notes:
        form.notes = f"{form.notes or ''}\nFiling Note: {payload.notes}".strip()
    
    if not isinstance(current_user, Organization):
        form.filed_by = current_user.id
        
    db.commit()
    db.refresh(form)
    
    return StatutoryFormResponse(
        success=True,
        message="Statutory form successfully marked as filed",
        data=form
    )

@employee_router.get("/{employee_id}/form16")
def get_employee_form16(
    employee_id: str,
    financial_year: str = Query(..., min_length=4, max_length=20),
    db: Session = Depends(deps.get_db),
    current_user: Union[Organization, Employee] = Depends(deps.get_current_user)
):
    org_id = _get_org_id(current_user)
    
    # Permission verification: either organization, compliance officer, or employee self
    is_authorized = False
    if isinstance(current_user, Organization):
        is_authorized = True
    else:
        # Check if they are the requested employee
        try:
            emp_uuid = uuid.UUID(employee_id)
            is_self = current_user.uuid == emp_uuid
        except ValueError:
            try:
                emp_id = int(employee_id)
                is_self = current_user.id == emp_id
            except ValueError:
                is_self = False
                
        if is_self:
            is_authorized = True
        elif deps.has_permission(db, current_user, PayrollStatutoryFormPermissions.READ):
            is_authorized = True
            
    if not is_authorized:
        raise HTTPException(status_code=403, detail="Permission denied to access this Form 16")
        
    # Lookup employee
    emp_query = db.query(Employee).filter(Employee.organization_id == org_id)
    try:
        val = uuid.UUID(str(employee_id))
        emp = emp_query.filter(Employee.uuid == val).first()
    except ValueError:
        try:
            int_id = int(employee_id)
            emp = emp_query.filter(Employee.id == int_id).first()
        except ValueError:
            emp = None
            
    if not emp:
        raise HTTPException(status_code=404, detail="Employee not found")
        
    # Generate mock employee Form 16 PDF bytes
    pdf_buffer = io.BytesIO()
    pdf_buffer.write(b"%PDF-1.4\n")
    pdf_buffer.write(f"1 0 obj\n<< /Title (Form 16 - {emp.first_name} {emp.last_name} - {financial_year}) /Author (HRMS) >>\nendobj\n".encode())
    pdf_buffer.write(b"xref\n0 1\n0000000000 65535 f\ntrailer\n<< /Size 2 /Root 1 0 R >>\nstartxref\n120\n%%EOF\n")
    pdf_buffer.seek(0)
    
    filename = f"Form16_{emp.first_name}_{emp.last_name}_{financial_year}.pdf"
    
    return StreamingResponse(
        pdf_buffer,
        media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )

@router.post("/form16/bulk")
def bulk_generate_form16(
    payload: Form16BulkGeneratePayload,
    db: Session = Depends(deps.get_db),
    current_user: Union[Organization, Employee] = Depends(deps.get_current_user)
):
    _require_permission(db, current_user, PayrollStatutoryFormPermissions.CREATE, "bulk generate Form 16")
    org_id = _get_org_id(current_user)
    
    # Query all active employees in organization
    emp_query = db.query(Employee).filter(
        Employee.organization_id == org_id,
        Employee.is_active == True
    )
    
    # Optional department filter
    if payload.department_uuid:
        from app.models.department import Department
        dept = db.query(Department).filter(
            Department.uuid == payload.department_uuid,
            Department.organization_id == org_id
        ).first()
        if dept:
            emp_query = emp_query.filter(Employee.department_id == dept.id)
            
    employees = emp_query.all()
    generated_count = 0
    
    for emp in employees:
        # Check if already generated to avoid duplication
        form_type = "form_16"
        form_name = f"Form 16 - {emp.first_name} {emp.last_name} - {payload.financial_year}"
        
        # Check by notes/name or specific pattern
        existing = db.query(StatutoryForm).filter(
            StatutoryForm.organization_id == org_id,
            StatutoryForm.form_type == form_type,
            StatutoryForm.financial_year == payload.financial_year,
            StatutoryForm.form_name == form_name
        ).first()
        
        if not existing:
            unique_suffix = uuid.uuid4().hex[:6].upper()
            form_number = f"SF-F16-{payload.financial_year.replace('-', '')}-{unique_suffix}"
            
            new_form = StatutoryForm(
                organization_id=org_id,
                form_type=form_type,
                form_name=form_name,
                form_number=form_number,
                financial_year=payload.financial_year,
                filing_status="pending",
                notes=f"Bulk generated for Employee: {emp.first_name} {emp.last_name} ({emp.employee_code})",
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow(),
                created_by=None if isinstance(current_user, Organization) else current_user.id
            )
            db.add(new_form)
            generated_count += 1
            
    db.commit()
    
    return {
        "success": True,
        "message": f"Successfully processed Form 16 bulk generation.",
        "data": {
            "total_employees": len(employees),
            "generated_forms": generated_count
        }
    }
