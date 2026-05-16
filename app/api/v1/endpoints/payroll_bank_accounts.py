import uuid
from typing import List, Optional, Union
from fastapi import APIRouter, Depends, HTTPException, Query, status, Request
from sqlalchemy.orm import Session, joinedload
from app.api import deps
from app.utils.payroll_audit import PayrollAuditService
from app.models.organization import Organization
from app.models.employee import Employee
from app.models.payroll import EmployeeBankAccount
from app.schemas.payroll_bank_accounts import (
    EmployeeBankAccountCreate,
    EmployeeBankAccountUpdate,
    EmployeeBankAccountSchema,
    EmployeeBankAccountResponse,
    EmployeeBankAccountListResponse,
    EmployeeBankAccountLookupSchema,
    EmployeeBankAccountLookupResponse
)
from app.core.permissions import PayrollBankAccountsPermissions

router = APIRouter()

def _get_org_id(current_user: Union[Organization, Employee]) -> int:
    return current_user.id if isinstance(current_user, Organization) else current_user.organization_id

def _require_permission(db: Session, current_user: Union[Organization, Employee], code: str, action_label: str):
    if isinstance(current_user, Organization):
        return
    if not deps.has_permission(db, current_user, code):
        raise HTTPException(status_code=403, detail=f"You do not have permission to {action_label} (requires code: {code})")

@router.get("/lookup", response_model=EmployeeBankAccountLookupResponse)
def lookup_bank_accounts(
    search: Optional[str] = None,
    employee_uuid: Optional[uuid.UUID] = None,
    db: Session = Depends(deps.get_db),
    current_user: Union[Organization, Employee] = Depends(deps.get_current_user)
):
    org_id = _get_org_id(current_user)
    
    query = db.query(EmployeeBankAccount).options(joinedload(EmployeeBankAccount.employee)).join(
        Employee, 
        EmployeeBankAccount.employee_id == Employee.id
    ).filter(Employee.organization_id == org_id, EmployeeBankAccount.is_active == True)
    
    if employee_uuid:
        query = query.filter(Employee.uuid == employee_uuid)
    
    if search:
        query = query.filter(EmployeeBankAccount.bank_name.ilike(f"%{search}%"))
        
    items = query.limit(50).all()
    
    lookup_data = []
    for item in items:
        lookup_data.append(EmployeeBankAccountLookupSchema(
            uuid=item.uuid,
            bank_name=item.bank_name,
            account_number=item.account_number[-4:].rjust(len(item.account_number), '*') if len(item.account_number) > 4 else item.account_number,
            employee_name=f"{item.employee.first_name} {item.employee.last_name}",
            is_primary=item.is_primary
        ))
        
    return {"success": True, "message": "Bank account lookup successful", "data": lookup_data}

@router.get("/", response_model=EmployeeBankAccountListResponse)
def get_bank_accounts(
    page: int = Query(1, ge=1),
    limit: int = Query(10, ge=1, le=100),
    search: Optional[str] = None,
    is_active: Optional[bool] = None,
    sort_by: Optional[str] = Query("created_at"),
    sort_order: Optional[str] = Query("desc"),
    db: Session = Depends(deps.get_db),
    current_user: Union[Organization, Employee] = Depends(deps.get_current_user)
):
    _require_permission(db, current_user, PayrollBankAccountsPermissions.READ, "list bank accounts")
    org_id = _get_org_id(current_user)
    
    query = db.query(EmployeeBankAccount).options(joinedload(EmployeeBankAccount.employee)).join(
        Employee, 
        EmployeeBankAccount.employee_id == Employee.id
    ).filter(Employee.organization_id == org_id)
    
    if is_active is not None:
        query = query.filter(EmployeeBankAccount.is_active == is_active)
    if search:
        query = query.filter(EmployeeBankAccount.bank_name.ilike(f"%{search}%"))

    # Sorting
    if sort_by:
        attr = getattr(EmployeeBankAccount, sort_by, None)
        if attr:
            if sort_order == "desc":
                query = query.order_by(attr.desc())
            else:
                query = query.order_by(attr.asc())
        elif sort_by == "employee_name":
            if sort_order == "desc":
                query = query.order_by(Employee.first_name.desc(), Employee.last_name.desc())
            else:
                query = query.order_by(Employee.first_name.asc(), Employee.last_name.asc())
    
    total_records = query.count()
    items = query.offset((page - 1) * limit).limit(limit).all()
    
    return EmployeeBankAccountListResponse(
        success=True, message="Bank accounts retrieved successfully",
        data=[EmployeeBankAccountSchema.model_validate(i) for i in items],
        pagination={'total_records': total_records, 'current_page': page, 'total_pages': (total_records + limit - 1) // limit if total_records > 0 else 0, 'page_size': limit}
    )

@router.post("/", response_model=EmployeeBankAccountResponse)
def create_bank_account(
    item_in: EmployeeBankAccountCreate,
    request: Request,
    db: Session = Depends(deps.get_db),
    current_user: Union[Organization, Employee] = Depends(deps.get_current_user)
):
    _require_permission(db, current_user, PayrollBankAccountsPermissions.CREATE, "create bank account")
    org_id = _get_org_id(current_user)
    
    # Resolve Employee UUID to ID
    employee = db.query(Employee).filter(Employee.uuid == item_in.employee_uuid, Employee.organization_id == org_id).first()
    if not employee:
        raise HTTPException(status_code=404, detail="Employee not found")
    
    if item_in.is_primary:
        db.query(EmployeeBankAccount).filter(EmployeeBankAccount.employee_id == employee.id).update({"is_primary": False})
    
    data = item_in.model_dump(exclude={"employee_uuid"})
    item = EmployeeBankAccount(
        **data,
        employee_id=employee.id
    )
    db.add(item)
    db.commit()
    db.refresh(item)
    _ = item.employee  # Trigger lazy load for schema mapping
    
    # Audit Log
    PayrollAuditService.log(
        db=db,
        current_user=current_user,
        action_type="bank_account_created",
        entity_type="bank_account",
        entity_id=item.id,
        employee_id=employee.id,
        after_state=PayrollAuditService.get_model_dict(item),
        change_summary=f"Added new {item.bank_name} account for {employee.first_name} {employee.last_name}",
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent")
    )
    db.commit() 
    
    return {"success": True, "message": "Bank account created successfully", "data": item}

@router.get("/{account_uuid}", response_model=EmployeeBankAccountResponse)
def get_bank_account(
    account_uuid: uuid.UUID,
    db: Session = Depends(deps.get_db),
    current_user: Union[Organization, Employee] = Depends(deps.get_current_user)
):
    _require_permission(db, current_user, PayrollBankAccountsPermissions.READ, "view bank account")
    item = db.query(EmployeeBankAccount).options(joinedload(EmployeeBankAccount.employee)).filter(EmployeeBankAccount.uuid == account_uuid).first()
    if not item:
        raise HTTPException(status_code=404, detail="Bank account not found")
    return {"success": True, "message": "Bank account retrieved successfully", "data": item}

@router.put("/{account_uuid}", response_model=EmployeeBankAccountResponse)
def update_bank_account(
    account_uuid: uuid.UUID,
    item_in: EmployeeBankAccountUpdate,
    request: Request,
    db: Session = Depends(deps.get_db),
    current_user: Union[Organization, Employee] = Depends(deps.get_current_user)
):
    _require_permission(db, current_user, PayrollBankAccountsPermissions.UPDATE, "update bank account")
    item = db.query(EmployeeBankAccount).options(joinedload(EmployeeBankAccount.employee)).filter(EmployeeBankAccount.uuid == account_uuid).first()
    if not item:
        raise HTTPException(status_code=404, detail="Bank account not found")
    
    if item_in.is_primary and not item.is_primary:
        db.query(EmployeeBankAccount).filter(EmployeeBankAccount.employee_id == item.employee_id).update({"is_primary": False})
        
    # Capture state before update
    before_state = PayrollAuditService.get_model_dict(item)
    
    for field, value in item_in.model_dump(exclude_unset=True).items():
        setattr(item, field, value)
    db.commit()
    db.refresh(item)
    
    # Audit Log
    PayrollAuditService.log(
        db=db,
        current_user=current_user,
        action_type="bank_account_updated",
        entity_type="bank_account",
        entity_id=item.id,
        employee_id=item.employee_id,
        before_state=before_state,
        after_state=PayrollAuditService.get_model_dict(item),
        change_summary=f"Updated bank account details for {item.employee.first_name}",
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent")
    )
    db.commit()
    
    return {"success": True, "message": "Bank account updated successfully", "data": item}

@router.delete("/{account_uuid}")
def delete_bank_account(
    account_uuid: uuid.UUID,
    request: Request,
    db: Session = Depends(deps.get_db),
    current_user: Union[Organization, Employee] = Depends(deps.get_current_user)
):
    _require_permission(db, current_user, PayrollBankAccountsPermissions.DELETE, "delete bank account")
    item = db.query(EmployeeBankAccount).options(joinedload(EmployeeBankAccount.employee)).filter(EmployeeBankAccount.uuid == account_uuid).first()
    if not item:
        raise HTTPException(status_code=404, detail="Bank account not found")
    
    before_state = PayrollAuditService.get_model_dict(item)
    item.is_active = False
    db.commit()
    
    # Audit Log
    PayrollAuditService.log(
        db=db,
        current_user=current_user,
        action_type="bank_account_deactivated",
        entity_type="bank_account",
        entity_id=item.id,
        employee_id=item.employee_id,
        before_state=before_state,
        after_state=PayrollAuditService.get_model_dict(item),
        change_summary=f"Deactivated bank account for {item.employee.first_name}",
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent")
    )
    db.commit()
    
    return {"success": True, "message": "Bank account deleted successfully"}