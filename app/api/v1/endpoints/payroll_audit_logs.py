import uuid
from typing import List, Optional, Union
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from sqlalchemy import and_, desc, asc
import io
import csv

from app.api import deps
from app.models.organization import Organization
from app.models.employee import Employee
from app.models.payroll import PayrollAuditLog, PayrollPeriod, Payslip, EmployeeSalary, EmployeeLoan
from app.schemas.payroll_audit_logs import PayrollAuditLogListResponse, PayrollAuditLogSchema
from app.core.permissions import PayrollAuditLogPermissions

router = APIRouter()

def _get_org_id(current_user: Union[Organization, Employee]) -> int:
    return current_user.id if isinstance(current_user, Organization) else current_user.organization_id

def _require_permission(db: Session, current_user: Union[Organization, Employee], code: str, action_label: str):
    if not isinstance(current_user, Organization) and not deps.has_permission(db, current_user, code):
        raise HTTPException(status_code=403, detail=f"You do not have permission to {action_label}")

@router.get("/", response_model=PayrollAuditLogListResponse)
def get_audit_logs(
    page: int = Query(1, ge=1),
    limit: int = Query(10, ge=1, le=100),
    action_type: Optional[str] = Query(None),
    entity_type: Optional[str] = Query(None),
    employee_uuid: Optional[uuid.UUID] = Query(None),
    from_date: Optional[datetime] = Query(None),
    to_date: Optional[datetime] = Query(None),
    sort_by: str = Query("performed_at"),
    order: str = Query("desc", regex="^(asc|desc)$"),
    db: Session = Depends(deps.get_db),
    current_user: Union[Organization, Employee] = Depends(deps.get_current_user)
):
    _require_permission(db, current_user, "127", "list audit logs")
    org_id = _get_org_id(current_user)
    
    query = db.query(PayrollAuditLog).filter(PayrollAuditLog.organization_id == org_id)
    
    if action_type: query = query.filter(PayrollAuditLog.action_type == action_type)
    if entity_type: query = query.filter(PayrollAuditLog.entity_type == entity_type)
    if employee_uuid:
        emp = db.query(Employee).filter(Employee.uuid == employee_uuid).first()
        if emp: query = query.filter(PayrollAuditLog.employee_id == emp.id)
    if from_date: query = query.filter(PayrollAuditLog.performed_at >= from_date)
    if to_date: query = query.filter(PayrollAuditLog.performed_at <= to_date)
    
    sort_attr = getattr(PayrollAuditLog, sort_by, PayrollAuditLog.performed_at)
    query = query.order_by(desc(sort_attr) if order == "desc" else asc(sort_attr))
    
    total_records = query.count()
    items = query.offset((page - 1) * limit).limit(limit).all()
    
    return {
        "success": True,
        "message": "Audit logs retrieved successfully",
        "data": [PayrollAuditLogSchema.model_validate(i) for i in items],
        "pagination": {
            "total_records": total_records,
            "current_page": page,
            "total_pages": (total_records + limit - 1) // limit if total_records > 0 else 0,
            "page_size": limit
        }
    }

@router.get("/export")
def export_audit_logs(
    action_type: Optional[str] = Query(None),
    from_date: Optional[datetime] = Query(None),
    to_date: Optional[datetime] = Query(None),
    db: Session = Depends(deps.get_db),
    current_user: Union[Organization, Employee] = Depends(deps.get_current_user)
):
    _require_permission(db, current_user, "127", "export audit logs")
    org_id = _get_org_id(current_user)
    
    query = db.query(PayrollAuditLog).filter(PayrollAuditLog.organization_id == org_id)
    if action_type: query = query.filter(PayrollAuditLog.action_type == action_type)
    if from_date: query = query.filter(PayrollAuditLog.performed_at >= from_date)
    if to_date: query = query.filter(PayrollAuditLog.performed_at <= to_date)
    
    logs = query.limit(1000).all()
    
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["Action", "Entity", "Performed At", "Summary"])
    for log in logs:
        writer.writerow([log.action_type, log.entity_type, log.performed_at, log.change_summary])
    
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=audit_logs.csv"}
    )

@router.get("/compliance-check")
def check_compliance(
    db: Session = Depends(deps.get_db),
    current_user: Union[Organization, Employee] = Depends(deps.get_current_user)
):
    _require_permission(db, current_user, "127", "check compliance")
    org_id = _get_org_id(current_user)
    violations = []
    
    # Example Rule: Payroll processed without approval
    unapproved_processed = db.query(PayrollPeriod).filter(
        PayrollPeriod.organization_id == org_id,
        PayrollPeriod.status == "processed",
        PayrollPeriod.approved_at == None
    ).all()
    
    for p in unapproved_processed:
        violations.append({"issue": f"Payroll period {p.period_code} processed without approval", "severity": "high", "entity_type": "payroll_period", "entity_id": p.id})
        
    return {"success": True, "message": "Compliance check completed", "data": violations}