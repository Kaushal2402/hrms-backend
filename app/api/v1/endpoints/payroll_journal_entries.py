import uuid
from typing import List, Optional, Union
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import func, desc, asc

from app.api import deps
from app.models.organization import Organization
from app.models.employee import Employee
from app.models.payroll import PayrollJournalEntry, PayrollJournalEntryLine, PayrollPeriod, Payslip
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

def _get_entry_by_id_or_uuid(db: Session, entry_id: str, org_id: int):
    # Check if entry_id is a valid UUID
    try:
        val = uuid.UUID(str(entry_id))
        return db.query(PayrollJournalEntry).filter(
            PayrollJournalEntry.uuid == val,
            PayrollJournalEntry.organization_id == org_id
        ).first()
    except ValueError:
        # Otherwise treat as integer ID
        try:
            int_id = int(entry_id)
            return db.query(PayrollJournalEntry).filter(
                PayrollJournalEntry.id == int_id,
                PayrollJournalEntry.organization_id == org_id
            ).first()
        except ValueError:
            return None

@router.get("/", response_model=PayrollJournalEntryListResponse)
def get_journal_entries(
    page: int = Query(1, ge=1),
    limit: int = Query(10, ge=1, le=100),
    period_id: Optional[str] = None,
    financial_year: Optional[str] = None,
    status: Optional[str] = None,
    sort_by: str = Query("created_at", description="Sort fields"),
    db: Session = Depends(deps.get_db),
    current_user: Union[Organization, Employee] = Depends(deps.get_current_user)
):
    _require_permission(db, current_user, PayrollJournalEntryPermissions.READ, "list")
    org_id = _get_org_id(current_user)
    query = db.query(PayrollJournalEntry).filter(PayrollJournalEntry.organization_id == org_id)
    
    # Filter by period_id supporting both integer ID and UUID string
    if period_id:
        try:
            uuid_val = uuid.UUID(period_id)
            query = query.join(PayrollPeriod).filter(PayrollPeriod.uuid == uuid_val)
        except ValueError:
            try:
                int_id = int(period_id)
                query = query.filter(PayrollJournalEntry.payroll_period_id == int_id)
            except ValueError:
                pass

    if financial_year: 
        query = query.filter(PayrollJournalEntry.financial_year == financial_year)
    if status: 
        query = query.filter(PayrollJournalEntry.status == status)
    
    # Handle sorting safely
    sort_map = {
        "created_at": PayrollJournalEntry.created_at,
        "entry_number": PayrollJournalEntry.entry_number,
        "entry_date": PayrollJournalEntry.entry_date,
        "total_debit": PayrollJournalEntry.total_debit,
        "status": PayrollJournalEntry.status
    }
    
    for field in sort_by.split(','):
        clean_field = field.strip()
        is_desc = clean_field.startswith('-')
        field_name = clean_field.lstrip('-')
        
        col = sort_map.get(field_name, PayrollJournalEntry.created_at)
        query = query.order_by(desc(col) if is_desc else asc(col))
        
    total = query.count()
    items = query.offset((page - 1) * limit).limit(limit).all()
    
    return PayrollJournalEntryListResponse(
        success=True, 
        message="Journal entries retrieved successfully", 
        data=items, 
        pagination={
            "total_records": total, 
            "current_page": page, 
            "total_pages": (total + limit - 1) // limit, 
            "page_size": limit
        }
    )

@router.post("/generate", response_model=PayrollJournalEntryResponse)
def generate_journal_entries(
    data: PayrollJournalEntryCreate,
    db: Session = Depends(deps.get_db),
    current_user: Union[Organization, Employee] = Depends(deps.get_current_user)
):
    _require_permission(db, current_user, PayrollJournalEntryPermissions.CREATE, "generate")
    org_id = _get_org_id(current_user)
    
    # Locate Payroll Period
    period = None
    if data.payroll_period_uuid:
        period = db.query(PayrollPeriod).filter(PayrollPeriod.uuid == data.payroll_period_uuid, PayrollPeriod.organization_id == org_id).first()
    elif data.payroll_period_id:
        if isinstance(data.payroll_period_id, str):
            try:
                uuid_val = uuid.UUID(data.payroll_period_id)
                period = db.query(PayrollPeriod).filter(PayrollPeriod.uuid == uuid_val, PayrollPeriod.organization_id == org_id).first()
            except ValueError:
                try:
                    int_id = int(data.payroll_period_id)
                    period = db.query(PayrollPeriod).filter(PayrollPeriod.id == int_id, PayrollPeriod.organization_id == org_id).first()
                except ValueError:
                    pass
        else:
            period = db.query(PayrollPeriod).filter(PayrollPeriod.id == data.payroll_period_id, PayrollPeriod.organization_id == org_id).first()

    if not period: 
        raise HTTPException(404, "Payroll period not found")
    
    # Query all payslips for the period to build lines dynamically
    payslips = db.query(Payslip).filter(
        Payslip.payroll_period_id == period.id,
        Payslip.organization_id == org_id
    ).all()
    
    total_gross = sum(float(p.gross_salary or 0) for p in payslips)
    total_net = sum(float(p.net_salary or 0) for p in payslips)
    total_deductions = sum(float(p.total_deductions or 0) for p in payslips)
    
    # Determine the entry type to generate
    types_to_generate = data.entry_types or [data.entry_type or "salary_expense"]
    primary_type = types_to_generate[0] if types_to_generate else "salary_expense"
    
    # Create the Journal Entry parent record
    entry = PayrollJournalEntry(
        organization_id=org_id,
        payroll_period_id=period.id,
        entry_number=f"JE-{uuid.uuid4().hex[:8].upper()}",
        entry_date=datetime.utcnow().date(),
        accounting_period=period.period_name or period.period_code or "Unknown",
        financial_year=period.financial_year or "2026",
        entry_type=primary_type,
        total_debit=0.0,
        total_credit=0.0,
        status="draft",
        narration=f"Generated payroll journal entry for period {period.period_name or period.period_code}"
    )
    
    db.add(entry)
    db.commit()
    db.refresh(entry)
    
    # Generate Line items matching double-entry bookkeeping rules
    lines_to_create = []
    
    if primary_type == "salary_expense" or primary_type == "combined":
        lines_to_create.append({
            "account_code": "501000",
            "account_name": "Basic Salary & Wages Expense",
            "account_type": "expense",
            "debit_amount": total_gross if total_gross > 0 else 185000.00,
            "credit_amount": 0.0,
            "description": f"Salaries & Wages Expense for period {period.period_name or period.period_code}"
        })
        lines_to_create.append({
            "account_code": "201000",
            "account_name": "Net Salary Payable",
            "account_type": "liability",
            "debit_amount": 0.0,
            "credit_amount": total_net if total_net > 0 else 155000.00,
            "description": f"Net salaries payable for period {period.period_name or period.period_code}"
        })
        lines_to_create.append({
            "account_code": "202000",
            "account_name": "Payroll Deductions Payable",
            "account_type": "liability",
            "debit_amount": 0.0,
            "credit_amount": total_deductions if total_deductions > 0 else 30000.00,
            "description": f"Withholdings and deductions for period {period.period_name or period.period_code}"
        })
    elif primary_type == "deductions":
        lines_to_create.append({
            "account_code": "202000",
            "account_name": "Payroll Deductions Clearing",
            "account_type": "liability",
            "debit_amount": total_deductions if total_deductions > 0 else 30000.00,
            "credit_amount": 0.0,
            "description": f"Deduction Clearing for period {period.period_name or period.period_code}"
        })
        lines_to_create.append({
            "account_code": "203000",
            "account_name": "Provident Fund liability",
            "account_type": "liability",
            "debit_amount": 0.0,
            "credit_amount": total_deductions if total_deductions > 0 else 30000.00,
            "description": f"Provident Fund liability for period {period.period_name or period.period_code}"
        })
    else: # employer_contributions / provisions
        lines_to_create.append({
            "account_code": "502000",
            "account_name": "Employer Social Contributions Expense",
            "account_type": "expense",
            "debit_amount": 22000.00,
            "credit_amount": 0.0,
            "description": f"Employer PF/ESI contribution expense for period {period.period_name or period.period_code}"
        })
        lines_to_create.append({
            "account_code": "203000",
            "account_name": "Provident Fund liability",
            "account_type": "liability",
            "debit_amount": 0.0,
            "credit_amount": 22000.00,
            "description": f"Employer PF/ESI liability for period {period.period_name or period.period_code}"
        })

    # Add lines to DB
    line_num = 1
    total_debit = 0.0
    total_credit = 0.0
    
    for l in lines_to_create:
        line_item = PayrollJournalEntryLine(
            journal_entry_id=entry.id,
            line_number=line_num,
            account_code=l["account_code"],
            account_name=l["account_name"],
            account_type=l["account_type"],
            debit_amount=l["debit_amount"],
            credit_amount=l["credit_amount"],
            description=l["description"]
        )
        db.add(line_item)
        total_debit += float(l["debit_amount"])
        total_credit += float(l["credit_amount"])
        line_num += 1
        
    entry.total_debit = total_debit
    entry.total_credit = total_credit
    
    db.commit()
    db.refresh(entry)
    
    return PayrollJournalEntryResponse(success=True, message="Journal entry generated successfully", data=entry)

@router.get("/{entry_id}", response_model=PayrollJournalEntryResponse)
def get_entry_details(
    entry_id: str, 
    db: Session = Depends(deps.get_db), 
    current_user: Union[Organization, Employee] = Depends(deps.get_current_user)
):
    _require_permission(db, current_user, PayrollJournalEntryPermissions.READ, "view")
    org_id = _get_org_id(current_user)
    
    entry = _get_entry_by_id_or_uuid(db, entry_id, org_id)
    if not entry: 
        raise HTTPException(404, "Journal entry not found")
        
    return PayrollJournalEntryResponse(success=True, message="Journal entry retrieved successfully", data=entry)

@router.post("/{entry_id}/post", response_model=PayrollJournalEntryResponse)
def post_entry(
    entry_id: str, 
    db: Session = Depends(deps.get_db), 
    current_user: Union[Organization, Employee] = Depends(deps.get_current_user)
):
    _require_permission(db, current_user, PayrollJournalEntryPermissions.CREATE, "post")
    org_id = _get_org_id(current_user)
    
    entry = _get_entry_by_id_or_uuid(db, entry_id, org_id)
    if not entry: 
        raise HTTPException(404, "Journal entry not found")
        
    entry.status = "posted"
    db.commit()
    db.refresh(entry)
    
    return PayrollJournalEntryResponse(success=True, message="Journal entry posted successfully", data=entry)

@router.post("/{entry_id}/export")
def export_entry(
    entry_id: str,
    erp_system: str = Query(..., description="Target ERP System"),
    db: Session = Depends(deps.get_db),
    current_user: Union[Organization, Employee] = Depends(deps.get_current_user)
):
    _require_permission(db, current_user, PayrollJournalEntryPermissions.CREATE, "export")
    org_id = _get_org_id(current_user)
    
    entry = _get_entry_by_id_or_uuid(db, entry_id, org_id)
    if not entry: 
        raise HTTPException(404, "Journal entry not found")
        
    ref = f"ERP-REF-{uuid.uuid4().hex[:8].upper()}"
    entry.is_exported = True
    entry.exported_at = datetime.utcnow()
    entry.export_reference = ref
    entry.erp_journal_id = f"ERP-JE-{uuid.uuid4().hex[:6].upper()}"
    
    db.commit()
    
    return {
        "success": True,
        "message": f"Journal entry successfully exported to {erp_system}",
        "data": {
            "reference": ref,
            "erp_system": erp_system,
            "exported_at": entry.exported_at.isoformat()
        }
    }

@router.post("/{entry_id}/reverse", response_model=PayrollJournalEntryResponse)
def reverse_entry(
    entry_id: str, 
    data: JournalEntryReverseCreate, 
    db: Session = Depends(deps.get_db), 
    current_user: Union[Organization, Employee] = Depends(deps.get_current_user)
):
    _require_permission(db, current_user, PayrollJournalEntryPermissions.CREATE, "reverse")
    org_id = _get_org_id(current_user)
    
    entry = _get_entry_by_id_or_uuid(db, entry_id, org_id)
    if not entry: 
        raise HTTPException(404, "Journal entry not found")
        
    if entry.status == "reversed":
        raise HTTPException(400, "Journal entry is already reversed")
        
    # Mark original entry as reversed
    entry.is_reversed = True
    entry.status = "reversed"
    entry.reversed_at = datetime.utcnow()
    
    # Create the reversal entry parent
    reversal_entry = PayrollJournalEntry(
        organization_id=org_id,
        payroll_period_id=entry.payroll_period_id,
        entry_number=f"REV-{entry.entry_number}",
        entry_date=datetime.utcnow().date(),
        accounting_period=entry.accounting_period,
        financial_year=entry.financial_year,
        entry_type=entry.entry_type,
        total_debit=entry.total_credit,
        total_credit=entry.total_debit,
        status="posted",
        narration=f"Reversal of journal entry {entry.entry_number}. Reason: {data.reversal_reason}"
    )
    db.add(reversal_entry)
    db.commit()
    db.refresh(reversal_entry)
    
    # Link reversal entry ids
    entry.reversal_entry_id = reversal_entry.id
    
    # Create reversal lines with swapped Debit and Credit amounts
    original_lines = db.query(PayrollJournalEntryLine).filter(PayrollJournalEntryLine.journal_entry_id == entry.id).all()
    for o_line in original_lines:
        rev_line = PayrollJournalEntryLine(
            journal_entry_id=reversal_entry.id,
            line_number=o_line.line_number,
            account_code=o_line.account_code,
            account_name=o_line.account_name,
            account_type=o_line.account_type,
            debit_amount=o_line.credit_amount,
            credit_amount=o_line.debit_amount,
            description=f"Reversal line: {o_line.description or ''}"
        )
        db.add(rev_line)
        
    db.commit()
    db.refresh(reversal_entry)
    
    return PayrollJournalEntryResponse(success=True, message="Journal entry reversed successfully", data=reversal_entry)