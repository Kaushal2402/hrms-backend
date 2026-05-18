import uuid
from typing import Optional, Union
from datetime import datetime, date
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session, joinedload

from app.api import deps
from app.models.organization import Organization
from app.models.employee import Employee
from app.models.payroll import Arrear, OneTimePayment
from app.schemas.payroll_arrears_one_time import (
    ArrearCreate, ArrearResponse, ArrearListResponse,
    OneTimePaymentCreate, OneTimePaymentResponse, OneTimePaymentListResponse,
)

router = APIRouter()

def _get_org_id(current_user: Union[Organization, Employee]) -> int:
    return current_user.id if isinstance(current_user, Organization) else current_user.organization_id

def _require_permission(db, current_user, code, action_label):
    if isinstance(current_user, Organization):
        return
    if not deps.has_permission(db, current_user, code):
        raise HTTPException(status_code=403, detail=f"You do not have permission to {action_label}")

def _get_employee_by_uuid(db: Session, employee_uuid: uuid.UUID, org_id: int) -> Employee:
    emp = db.query(Employee).filter(
        Employee.uuid == employee_uuid,
        Employee.organization_id == org_id,
    ).first()
    if not emp:
        raise HTTPException(status_code=404, detail="Employee not found")
    return emp

# ─── Arrears ──────────────────────────────────────────────────────────────────

@router.get("/arrears", response_model=ArrearListResponse)
def get_arrears(
    employee_uuid: Optional[uuid.UUID] = None,
    status: Optional[str] = None,
    from_date: Optional[date] = None,
    to_date: Optional[date] = None,
    page: int = Query(1, ge=1),
    limit: int = Query(10, ge=1, le=100),
    sort_by: str = Query("created_at"),
    sort_order: str = Query("desc"),
    db: Session = Depends(deps.get_db),
    current_user: Union[Organization, Employee] = Depends(deps.get_current_user),
):
    _require_permission(db, current_user, "101", "list arrears")
    query = (
        db.query(Arrear)
        .options(joinedload(Arrear.employee))
        .filter(Arrear.organization_id == _get_org_id(current_user))
    )
    if employee_uuid:
        query = query.join(Employee, Arrear.employee_id == Employee.id).filter(Employee.uuid == employee_uuid)
    if status:
        query = query.filter(Arrear.status == status)
    if from_date:
        query = query.filter(Arrear.arrear_from_date >= from_date)
    if to_date:
        query = query.filter(Arrear.arrear_to_date <= to_date)

    allowed_sort = ["created_at", "arrear_amount", "amount", "arrear_number", "status"]
    sort_field = sort_by if sort_by in allowed_sort else "created_at"
    
    if sort_field == "amount":
        sort_field = "arrear_amount"

    if sort_order.lower() == "asc":
        query = query.order_by(getattr(Arrear, sort_field).asc())
    else:
        query = query.order_by(getattr(Arrear, sort_field).desc())

    total_records = query.count()
    items = (
        query.offset((page - 1) * limit)
        .limit(limit)
        .all()
    )
    return ArrearListResponse(
        success=True,
        message="Arrears retrieved successfully",
        data=items,
        pagination={
            "total_records": total_records,
            "current_page": page,
            "total_pages": (total_records + limit - 1) // limit,
            "page_size": limit,
        },
    )

@router.post("/arrears", response_model=ArrearResponse)
def create_arrear(
    item_in: ArrearCreate,
    db: Session = Depends(deps.get_db),
    current_user: Union[Organization, Employee] = Depends(deps.get_current_user),
):
    _require_permission(db, current_user, "102", "create arrears")
    org_id = _get_org_id(current_user)
    emp = _get_employee_by_uuid(db, item_in.employee_uuid, org_id)

    data = item_in.model_dump(exclude={"employee_uuid"})
    arrear = Arrear(
        organization_id=org_id,
        employee_id=emp.id,
        arrear_number=f"AR-{emp.employee_code}-{datetime.utcnow().strftime('%Y%m')}",
        **data,
    )
    db.add(arrear)
    db.commit()
    db.refresh(arrear)
    getattr(arrear, "employee")
    return {"success": True, "message": "Arrear created successfully", "data": arrear}

@router.get("/arrears/{arrear_uuid}", response_model=ArrearResponse)
def get_arrear(
    arrear_uuid: uuid.UUID,
    db: Session = Depends(deps.get_db),
    current_user: Union[Organization, Employee] = Depends(deps.get_current_user),
):
    _require_permission(db, current_user, "101", "view arrears")
    item = (
        db.query(Arrear)
        .options(joinedload(Arrear.employee))
        .filter(Arrear.uuid == arrear_uuid, Arrear.organization_id == _get_org_id(current_user))
        .first()
    )
    if not item:
        raise HTTPException(404, "Arrear not found")
    return {"success": True, "message": "Arrear retrieved successfully", "data": item}

@router.post("/arrears/{arrear_uuid}/approve", response_model=ArrearResponse)
def approve_arrear(
    arrear_uuid: uuid.UUID,
    db: Session = Depends(deps.get_db),
    current_user: Union[Organization, Employee] = Depends(deps.get_current_user),
):
    _require_permission(db, current_user, "103", "approve arrears")
    item = (
        db.query(Arrear)
        .options(joinedload(Arrear.employee))
        .filter(Arrear.uuid == arrear_uuid, Arrear.organization_id == _get_org_id(current_user))
        .first()
    )
    if not item:
        raise HTTPException(404, "Arrear not found")
    item.status = "APPROVED"
    item.approved_at = datetime.utcnow()
    db.commit()
    db.refresh(item)
    getattr(item, "employee")
    return {"success": True, "message": "Arrear approved successfully", "data": item}

# ─── One-Time Payments ────────────────────────────────────────────────────────

@router.get("/one-time-payments", response_model=OneTimePaymentListResponse)
def get_otps(
    employee_uuid: Optional[uuid.UUID] = None,
    payment_type: Optional[str] = None,
    status: Optional[str] = None,
    page: int = Query(1, ge=1),
    limit: int = Query(10, ge=1, le=100),
    sort_by: str = Query("created_at"),
    db: Session = Depends(deps.get_db),
    current_user: Union[Organization, Employee] = Depends(deps.get_current_user),
):
    _require_permission(db, current_user, "101", "list payments")
    query = (
        db.query(OneTimePayment)
        .options(joinedload(OneTimePayment.employee))
        .filter(OneTimePayment.organization_id == _get_org_id(current_user))
    )
    if employee_uuid:
        query = query.join(Employee, OneTimePayment.employee_id == Employee.id).filter(Employee.uuid == employee_uuid)
    if payment_type:
        query = query.filter(OneTimePayment.payment_type == payment_type)
    if status:
        query = query.filter(OneTimePayment.status == status)

    total_records = query.count()
    items = (
        query.order_by(getattr(OneTimePayment, sort_by, OneTimePayment.created_at))
        .offset((page - 1) * limit)
        .limit(limit)
        .all()
    )
    return OneTimePaymentListResponse(
        success=True,
        message="One-time payments retrieved successfully",
        data=items,
        pagination={
            "total_records": total_records,
            "current_page": page,
            "total_pages": (total_records + limit - 1) // limit,
            "page_size": limit,
        },
    )

@router.post("/one-time-payments", response_model=OneTimePaymentResponse)
def create_otp(
    item_in: OneTimePaymentCreate,
    db: Session = Depends(deps.get_db),
    current_user: Union[Organization, Employee] = Depends(deps.get_current_user),
):
    _require_permission(db, current_user, "102", "create payments")
    org_id = _get_org_id(current_user)
    emp = _get_employee_by_uuid(db, item_in.employee_uuid, org_id)

    data = item_in.model_dump(exclude={"employee_uuid"})
    otp = OneTimePayment(
        organization_id=org_id,
        employee_id=emp.id,
        payment_number=f"OTP-{emp.employee_code}-{int(datetime.utcnow().timestamp())}",
        **data,
    )
    db.add(otp)
    db.commit()
    db.refresh(otp)
    getattr(otp, "employee")
    return {"success": True, "message": "One-time payment created successfully", "data": otp}

@router.get("/one-time-payments/{payment_uuid}", response_model=OneTimePaymentResponse)
def get_otp(
    payment_uuid: uuid.UUID,
    db: Session = Depends(deps.get_db),
    current_user: Union[Organization, Employee] = Depends(deps.get_current_user),
):
    _require_permission(db, current_user, "101", "get payment details")
    item = (
        db.query(OneTimePayment)
        .options(joinedload(OneTimePayment.employee))
        .filter(OneTimePayment.uuid == payment_uuid, OneTimePayment.organization_id == _get_org_id(current_user))
        .first()
    )
    if not item:
        raise HTTPException(404, "One-time payment not found")
    getattr(item, "employee")
    return {"success": True, "message": "One-time payment retrieved successfully", "data": item}

@router.post("/one-time-payments/{payment_uuid}/approve", response_model=OneTimePaymentResponse)
def approve_otp(
    payment_uuid: uuid.UUID,
    db: Session = Depends(deps.get_db),
    current_user: Union[Organization, Employee] = Depends(deps.get_current_user),
):
    _require_permission(db, current_user, "103", "approve payments")
    item = (
        db.query(OneTimePayment)
        .options(joinedload(OneTimePayment.employee))
        .filter(OneTimePayment.uuid == payment_uuid, OneTimePayment.organization_id == _get_org_id(current_user))
        .first()
    )
    if not item:
        raise HTTPException(404, "Payment not found")
    item.status = "APPROVED"
    item.approved_at = datetime.utcnow()
    db.commit()
    db.refresh(item)
    getattr(item, "employee")
    return {"success": True, "message": "One-time payment approved successfully", "data": item}
