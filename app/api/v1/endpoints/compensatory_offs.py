import uuid
from datetime import date, datetime, timedelta
from typing import List, Optional, Union
from fastapi import APIRouter, Depends, Query, status, HTTPException
from sqlalchemy.orm import Session, joinedload, contains_eager
from sqlalchemy import or_, and_

from app.api import deps
from app.models.attendance import CompensatoryOff, LeaveApplication
from app.models.employee import Employee, Department
from app.models.organization import Organization
from app.schemas.leave import (
    CompensatoryOffListResponse, CompensatoryOffCreate, 
    CompensatoryOffResponse, CompensatoryOffUtilizeRequest
)
from fastapi.responses import JSONResponse
from datetime import timedelta

router = APIRouter()

@router.get("/", response_model=CompensatoryOffListResponse)
def list_compensatory_offs(
    db: Session = Depends(deps.get_db),
    current_org: Organization = Depends(deps.get_current_org),
    current_user: Union[Organization, Employee] = Depends(deps.get_current_user),
    authorized: bool = Depends(deps.check_permission("51")),
    employee_uuid: Optional[uuid.UUID] = Query(None, description="Filter by employee UUID"),
    is_utilized: Optional[bool] = Query(None, description="Filter by utilization status"),
    is_expired: Optional[bool] = Query(None, description="Filter by expiry status"),
    department_uuid: Optional[uuid.UUID] = Query(None, description="Filter by department UUID"),
    search: Optional[str] = Query(None, description="Search by employee name or code"),
    sort_by: str = Query("worked_date", description="Sort by 'worked_date' or 'employee'"),
    order: str = Query("desc", description="Sort order ('asc' or 'desc')"),
    page: int = Query(1, ge=1, description="Page number"),
    limit: int = Query(10, ge=1, description="Items per page")
):
    """
    Retrieve a list of compensatory off credits with filtering and pagination.
    """
    # 1. RBAC: If Employee, force filter by self
    if isinstance(current_user, Employee):
        employee_uuid = current_user.uuid

    query = db.query(CompensatoryOff).filter(
        CompensatoryOff.organization_id == current_org.id
    )

    # 1. Base Query & Basic Filtering
    filters = [CompensatoryOff.organization_id == current_org.id]
    
    if is_utilized is not None:
        filters.append(CompensatoryOff.is_utilized == is_utilized)
    
    if is_expired is not None:
        filters.append(CompensatoryOff.is_expired == is_expired)

    # 2. Employee Mandatory Filter
    if employee_uuid:
        employee = db.query(Employee).filter(
            Employee.uuid == employee_uuid,
            Employee.organization_id == current_org.id
        ).first()
        if employee:
            filters.append(CompensatoryOff.employee_id == employee.id)
        else:
            return CompensatoryOffListResponse(
                success=True,
                message="Employee not found",
                data=[],
                pagination={"total_records": 0, "current_page": page, "total_pages": 0, "page_size": limit}
            )

    query = db.query(CompensatoryOff).filter(*filters)

    # 3. Advanced Filtering & Joins
    employee_joined = False
    
    # Always join employee if search or sort-by-employee to keep query consistent
    if search or department_uuid or sort_by == "employee":
        query = query.join(CompensatoryOff.employee)
        employee_joined = True
        
        if department_uuid:
            query = query.join(Employee.department).filter(
                Department.uuid == department_uuid
            )
        
        if search:
            search_val = f"%{search}%"
            query = query.filter(
                or_(
                    Employee.first_name.ilike(search_val),
                    Employee.last_name.ilike(search_val),
                    Employee.employee_code.ilike(search_val)
                )
            )

    # 4. Sorting
    if sort_by == "employee":
        if order.lower() == "asc":
            query = query.order_by(Employee.first_name.asc(), Employee.last_name.asc())
        else:
            query = query.order_by(Employee.first_name.desc(), Employee.last_name.desc())
    else: # worked_date
        if order.lower() == "asc":
            query = query.order_by(CompensatoryOff.worked_date.asc())
        else:
            query = query.order_by(CompensatoryOff.worked_date.desc())

    # 5. Result Execution
    total_records = query.count()
    total_pages = (total_records + limit - 1) // limit
    skip = (page - 1) * limit

    if employee_joined:
        records = query.options(
            contains_eager(CompensatoryOff.employee)
        ).offset(skip).limit(limit).all()
    else:
        records = query.options(
            joinedload(CompensatoryOff.employee)
        ).offset(skip).limit(limit).all()

    return CompensatoryOffListResponse(
        success=True,
        message="Compensatory off records retrieved successfully",
        data=records,
        pagination={
            "total_records": total_records,
            "current_page": page,
            "total_pages": total_pages,
            "page_size": limit
        }
    )

@router.post("/", response_model=CompensatoryOffResponse)
def create_compensatory_off(
    comp_off_in: CompensatoryOffCreate,
    db: Session = Depends(deps.get_db),
    current_org: Organization = Depends(deps.get_current_org),
    authorized: bool = Depends(deps.check_permission("52"))
):
    """
    Manually credit a compensatory off to an employee.
    """
    # 1. Resolve Employee
    employee = db.query(Employee).filter(
        Employee.uuid == comp_off_in.employee_uuid,
        Employee.organization_id == current_org.id
    ).first()
    
    if not employee:
        return JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND,
            content={"success": False, "message": "Employee not found", "data": None}
        )

    # 2. Check for duplicate credit for same date
    existing = db.query(CompensatoryOff).filter(
        CompensatoryOff.employee_id == employee.id,
        CompensatoryOff.worked_date == comp_off_in.worked_date,
        CompensatoryOff.organization_id == current_org.id
    ).first()
    
    if existing:
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={"success": False, "message": f"Comp-off already credited for {comp_off_in.worked_date}", "data": None}
        )

    # 3. Calculate Expiry
    expiry_date = comp_off_in.worked_date + timedelta(days=comp_off_in.expiry_days)
    
    # 4. Create Record
    comp_off = CompensatoryOff(
        organization_id=current_org.id,
        employee_id=employee.id,
        worked_date=comp_off_in.worked_date,
        comp_off_days=comp_off_in.comp_off_days,
        source_type=comp_off_in.source_type,
        reason=comp_off_in.reason,
        credited_date=date.today(),
        expiry_date=expiry_date,
        remaining_days=comp_off_in.comp_off_days,
        is_utilized=False,
        is_expired=False
    )
    
    db.add(comp_off)
    db.commit()
    db.refresh(comp_off)
    
    # Reload with relationships
    comp_off = db.query(CompensatoryOff).filter(CompensatoryOff.id == comp_off.id).options(
        joinedload(CompensatoryOff.employee)
    ).first()
    
    return CompensatoryOffResponse(
        success=True,
        message="Compensatory off credited successfully",
        data=comp_off
    )


@router.get("/expiring", response_model=CompensatoryOffListResponse)
def get_expiring_compensatory_offs(
    days: int = Query(30, ge=1, description="Number of days from today to check for expiry"),
    employee_uuid: Optional[uuid.UUID] = Query(None, description="Filter by employee UUID"),
    department_uuid: Optional[uuid.UUID] = Query(None, description="Filter by department UUID"),
    search: Optional[str] = Query(None, description="Search by employee name or code"),
    sort_by: str = Query("expiry_date", description="Sort by 'expiry_date' or 'employee'"),
    order: str = Query("asc", description="Sort order ('asc' or 'desc')"),
    db: Session = Depends(deps.get_db),
    current_org: Organization = Depends(deps.get_current_org),
    current_user: Union[Organization, Employee] = Depends(deps.get_current_user),
    authorized: bool = Depends(deps.check_permission("51")),
    page: int = Query(1, ge=1, description="Page number"),
    limit: int = Query(10, ge=1, description="Items per page")
):
    """
    Get compensatory off credits that are expiring within the specified number of days.
    """
    # 1. RBAC: If Employee, force filter by self
    if isinstance(current_user, Employee):
        employee_uuid = current_user.uuid

    # 2. Base Query & Filters
    today = date.today()
    expiry_threshold = today + timedelta(days=days)

    filters = [
        CompensatoryOff.organization_id == current_org.id,
        CompensatoryOff.is_utilized == False,
        CompensatoryOff.is_expired == False,
        CompensatoryOff.remaining_days > 0,
        CompensatoryOff.expiry_date >= today,
        CompensatoryOff.expiry_date <= expiry_threshold
    ]

    if employee_uuid:
        employee = db.query(Employee).filter(
            Employee.uuid == employee_uuid,
            Employee.organization_id == current_org.id
        ).first()
        if employee:
            filters.append(CompensatoryOff.employee_id == employee.id)
        else:
            return CompensatoryOffListResponse(
                success=True,
                message="Employee not found",
                data=[],
                pagination={"total_records": 0, "current_page": page, "total_pages": 0, "page_size": limit}
            )

    query = db.query(CompensatoryOff).filter(*filters)

    # 3. Joins for Search/Department/Sorting
    employee_joined = False
    
    if search or department_uuid or sort_by == "employee":
        query = query.join(CompensatoryOff.employee)
        employee_joined = True
        
        if department_uuid:
            query = query.join(Employee.department).filter(
                Department.uuid == department_uuid
            )
        
        if search:
            search_val = f"%{search}%"
            query = query.filter(
                or_(
                    Employee.first_name.ilike(search_val),
                    Employee.last_name.ilike(search_val),
                    Employee.employee_code.ilike(search_val)
                )
            )

    # 4. Sorting
    if sort_by == "employee":
        if order.lower() == "asc":
            query = query.order_by(Employee.first_name.asc(), Employee.last_name.asc())
        else:
            query = query.order_by(Employee.first_name.desc(), Employee.last_name.desc())
    else: # expiry_date
        if order.lower() == "asc":
            query = query.order_by(CompensatoryOff.expiry_date.asc())
        else:
            query = query.order_by(CompensatoryOff.expiry_date.desc())

    # 5. Result Execution
    total_records = query.count()
    total_pages = (total_records + limit - 1) // limit
    skip = (page - 1) * limit

    if employee_joined:
        records = query.options(
            contains_eager(CompensatoryOff.employee)
        ).offset(skip).limit(limit).all()
    else:
        records = query.options(
            joinedload(CompensatoryOff.employee)
        ).offset(skip).limit(limit).all()

    return CompensatoryOffListResponse(
        success=True,
        message=f"Compensatory off credits expiring within {days} days retrieved",
        data=records,
        pagination={
            "total_records": total_records,
            "current_page": page,
            "total_pages": total_pages,
            "page_size": limit
        }
    )
