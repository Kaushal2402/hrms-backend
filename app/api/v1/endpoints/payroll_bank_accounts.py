import uuid
from typing import List, Optional, Union
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from app.api import deps
from app.models.organization import Organization
from app.models.employee import Employee
from app.models.payroll import EmployeeBankAccount
from app.schemas.payroll_bank_accounts import (
    EmployeeBankAccountCreate,
    EmployeeBankAccountUpdate,
    EmployeeBankAccountSchema,
    EmployeeBankAccountResponse,
    EmployeeBankAccountListResponse
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

@router.get("/", response_model=EmployeeBankAccountListResponse)
def get_bank_accounts(
    page: int = Query(1, ge=1),
    limit: int = Query(10, ge=1, le=100),
    search: Optional[str] = None,
    is_active: Optional[bool] = None,
    db: Session = Depends(deps.get_db),
    current_user: Union[Organization, Employee] = Depends(deps.get_current_user)
):
    _require_permission(db, current_user, PayrollBankAccountsPermissions.READ, "list bank accounts")
    org_id = _get_org_id(current_user)
    
    query = db.query(EmployeeBankAccount).join(Employee).filter(Employee.organization_id == org_id)
    
    if is_active is not None:
        query = query.filter(EmployeeBankAccount.is_active == is_active)
    if search:
        query = query.filter(EmployeeBankAccount.bank_name.ilike(f"%{search}%"))
        
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
    db: Session = Depends(deps.get_db),
    current_user: Union[Organization, Employee] = Depends(deps.get_current_user)
):
    _require_permission(db, current_user, PayrollBankAccountsPermissions.CREATE, "create bank account")
    
    if item_in.is_primary:
        db.query(EmployeeBankAccount).filter(EmployeeBankAccount.employee_id == item_in.employee_id).update({"is_primary": False})
    
    item = EmployeeBankAccount(**item_in.model_dump())
    db.add(item)
    db.commit()
    db.refresh(item)
    return {"success": True, "message": "Bank account created successfully", "data": item}

@router.get("/{account_uuid}", response_model=EmployeeBankAccountResponse)
def get_bank_account(
    account_uuid: uuid.UUID,
    db: Session = Depends(deps.get_db),
    current_user: Union[Organization, Employee] = Depends(deps.get_current_user)
):
    _require_permission(db, current_user, PayrollBankAccountsPermissions.READ, "view bank account")
    item = db.query(EmployeeBankAccount).filter(EmployeeBankAccount.uuid == account_uuid).first()
    if not item:
        raise HTTPException(status_code=404, detail="Bank account not found")
    return {"success": True, "message": "Bank account retrieved successfully", "data": item}

@router.put("/{account_uuid}", response_model=EmployeeBankAccountResponse)
def update_bank_account(
    account_uuid: uuid.UUID,
    item_in: EmployeeBankAccountUpdate,
    db: Session = Depends(deps.get_db),
    current_user: Union[Organization, Employee] = Depends(deps.get_current_user)
):
    _require_permission(db, current_user, PayrollBankAccountsPermissions.UPDATE, "update bank account")
    item = db.query(EmployeeBankAccount).filter(EmployeeBankAccount.uuid == account_uuid).first()
    if not item:
        raise HTTPException(status_code=404, detail="Bank account not found")
    
    if item_in.is_primary and not item.is_primary:
        db.query(EmployeeBankAccount).filter(EmployeeBankAccount.employee_id == item.employee_id).update({"is_primary": False})
        
    for field, value in item_in.model_dump(exclude_unset=True).items():
        setattr(item, field, value)
    db.commit()
    db.refresh(item)
    return {"success": True, "message": "Bank account updated successfully", "data": item}

@router.delete("/{account_uuid}")
def delete_bank_account(
    account_uuid: uuid.UUID,
    db: Session = Depends(deps.get_db),
    current_user: Union[Organization, Employee] = Depends(deps.get_current_user)
):
    _require_permission(db, current_user, PayrollBankAccountsPermissions.DELETE, "delete bank account")
    item = db.query(EmployeeBankAccount).filter(EmployeeBankAccount.uuid == account_uuid).first()
    if not item:
        raise HTTPException(status_code=404, detail="Bank account not found")
    item.is_active = False
    db.commit()
    return {"success": True, "message": "Bank account deleted successfully"}