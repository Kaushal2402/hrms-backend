import uuid
from typing import List, Optional, Union
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import func, desc, asc

from app.api import deps
from app.models.organization import Organization
from app.models.employee import Employee
from app.models.payroll import PayrollJournalEntry, PayrollJournalEntryLine, PayrollPeriod, Payslip, PayslipComponent
from app.schemas.payroll_journal_entries import (
    PayrollJournalEntrySchema, PayrollJournalEntryResponse, 
    PayrollJournalEntryListResponse, PayrollJournalEntryCreate, JournalEntryReverseCreate
)
from app.core.permissions import PayrollJournalEntryPermissions

router = APIRouter()

def _get_org_id(current_user: Union[Organization, Employee]) -> int:
    return current_user.id if isinstance(current_user, Organization) else current_user.organization_id

def _require_permission(db: Session, current_user: Union[Organization, Employee], code: str, action: str):
    if not isinstance(current_user, Organization) and not deps.has_permission(db, current_user, code):
        raise HTTPException(status_code=403, detail=f"Permission denied: {action}")

@router.get("/", response_model=PayrollJournalEntryListResponse)
def get_journal_entries(
    page: int = Query(1, ge=1),
    limit: int = Query(10, ge=1, le=100),
    period_id: Optional[int] = None,
    financial_year: Optional[str] = None,
    status: Optional[str] = None,
    sort_by: str = Query("created_at", description="Comma-separated fields"),
    db: Session = Depends(deps.get_db),
    current_user: Union[Organization, Employee] = Depends(deps.get_current_user)
):
    _require_permission(db, current_user, PayrollJournalEntryPermissions.READ, "list")
    org_id = _get_org_id(current_user)
    query = db.query(PayrollJournalEntry).filter(PayrollJournalEntry.organization_id == org_id)
    
    if period_id: query = query.filter(PayrollJournalEntry.payroll_period_id == period_id)
    if financial_year: query = query.filter(PayrollJournalEntry.financial_year == financial_year)
    if status: query = query.filter(PayrollJournalEntry.status == status)
    
    for field in sort_by.split(','):
        query = query.order_by(desc(field) if field.startswith('-') else asc(field))
        
    total = query.count()
    items = query.offset((page - 1) * limit).limit(limit).all()
    return PayrollJournalEntryListResponse(success=True, message="Journal entries retrieved successfully", data=items, pagination={"total_records": total, "current_page": page, "total_pages": (total + limit - 1) // limit, "page_size": limit})

@router.post("/generate", response_model=PayrollJournalEntryResponse)
def generate_journal_entries(
    data: PayrollJournalEntryCreate,
    db: Session = Depends(deps.get_db),
    current_user: Union[Organization, Employee] = Depends(deps.get_current_user)
):
    _require_permission(db, current_user, PayrollJournalEntryPermissions.CREATE, "generate")
    org_id = _get_org_id(current_user)
    period = db.query(PayrollPeriod).filter(PayrollPeriod.id == data.payroll_period_id, PayrollPeriod.organization_id == org_id).first()
    if not period: raise HTTPException(404, "Period not found")
    
    entry = PayrollJournalEntry(
        organization_id=org_id, payroll_period_id=period.id, entry_number=f"JE-{uuid.uuid4().hex[:8].upper()}",
        entry_date=func.now(), accounting_period=period.period_code, financial_year=period.financial_year,
        entry_type=data.entry_type, total_debit=0, total_credit=0, status="draft"
    )
    db.add(entry)
    db.commit()
    db.refresh(entry)
    return PayrollJournalEntryResponse(success=True, message="Journal entry generated successfully", data=entry)

@router.get("/{entry_uuid}", response_model=PayrollJournalEntryResponse)
def get_entry_details(entry_uuid: uuid.UUID, db: Session = Depends(deps.get_db), current_user: Union[Organization, Employee] = Depends(deps.get_current_user)):
    _require_permission(db, current_user, PayrollJournalEntryPermissions.READ, "view")
    entry = db.query(PayrollJournalEntry).filter(PayrollJournalEntry.uuid == entry_uuid, PayrollJournalEntry.organization_id == _get_org_id(current_user)).first()
    if not entry: raise HTTPException(404, "Entry not found")
    return PayrollJournalEntryResponse(success=True, message="Journal entry retrieved successfully", data=entry)

@router.post("/{entry_uuid}/post", response_model=PayrollJournalEntryResponse)
def post_entry(entry_uuid: uuid.UUID, db: Session = Depends(deps.get_db), current_user: Union[Organization, Employee] = Depends(deps.get_current_user)):
    _require_permission(db, current_user, PayrollJournalEntryPermissions.CREATE, "post")
    entry = db.query(PayrollJournalEntry).filter(PayrollJournalEntry.uuid == entry_uuid, PayrollJournalEntry.organization_id == _get_org_id(current_user)).first()
    if not entry: raise HTTPException(404, "Entry not found")
    entry.status = "posted"
    db.commit()
    return PayrollJournalEntryResponse(success=True, message="Journal entry posted successfully", data=entry)

@router.post("/{entry_uuid}/reverse", response_model=PayrollJournalEntryResponse)
def reverse_entry(entry_uuid: uuid.UUID, data: JournalEntryReverseCreate, db: Session = Depends(deps.get_db), current_user: Union[Organization, Employee] = Depends(deps.get_current_user)):
    _require_permission(db, current_user, PayrollJournalEntryPermissions.CREATE, "reverse")
    entry = db.query(PayrollJournalEntry).filter(PayrollJournalEntry.uuid == entry_uuid, PayrollJournalEntry.organization_id == _get_org_id(current_user)).first()
    if not entry: raise HTTPException(404, "Entry not found")
    entry.is_reversed = True
    entry.status = "reversed"
    db.commit()
    return PayrollJournalEntryResponse(success=True, message="Journal entry reversed successfully", data=entry)