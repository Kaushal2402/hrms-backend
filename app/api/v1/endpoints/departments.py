import uuid
from datetime import datetime
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from app.api import deps
from app.models.employee import Department, Employee
from app.schemas.department import (
    DepartmentSchema, 
    DepartmentListResponse, 
    DepartmentCreate, 
    DepartmentUpdate,
    DepartmentResponse,
    DepartmentDetailResponse,
    DepartmentDetailSchema,
    DepartmentDeleteResponse,
    DepartmentHierarchyListResponse,
    DepartmentHierarchySchema
)
from app.schemas.employee import EmployeeListResponse
from app.models.organization import Organization
from app.core.permissions import DepartmentPermissions

router = APIRouter()

# ... (rest of code)
@router.get("/selection", response_model=DepartmentListResponse)
def get_departments_for_selection(
    db: Session = Depends(deps.get_db),
    current_org: Organization = Depends(deps.get_current_org),
    search: Optional[str] = Query(None, description="Search by Department Name or Code"),
    limit: int = Query(100, ge=1, description="Limit selection results")
):
    """
    Get all departments for selection (dropdown). 
    Accessible by all authenticated users (Organization OR Employee).
    """
    query = db.query(Department).filter(
        Department.organization_id == current_org.id,
        Department.is_deleted == False,
        Department.is_active == True
    )
    
    if search:
        search_term = f"%{search}%"
        query = query.filter(
            (Department.department_name.ilike(search_term)) |
            (Department.department_code.ilike(search_term))
        )
        
    departments = query.order_by(Department.department_name.asc()).limit(limit).all()
    
    return DepartmentListResponse(
        success=True,
        message="Departments for selection retrieved successfully",
        data=departments
    )


@router.get("/", response_model=DepartmentListResponse, dependencies=[Depends(deps.check_permission(DepartmentPermissions.READ))])
def list_departments(
    db: Session = Depends(deps.get_db),
    current_org: Organization = Depends(deps.get_current_org),
    is_active: Optional[bool] = Query(None, description="Filter by active status"),
    parent_department_id: Optional[int] = Query(None, description="Filter by parent department"),
    page: Optional[int] = Query(None, ge=1, description="Page number"),
    limit: int = Query(10, ge=1, description="Items per page"),
    sort_by: Optional[str] = Query(None, description="Sort by id, department_code, department_name, is_active"),
    sort_order: Optional[str] = Query("asc", regex="^(asc|desc)$", description="Sort order (asc or desc)"),
    search: Optional[str] = Query(None, description="Search by Department Name"),
):
    """
    List all departments with advanced sorting, filtering, and search.
    """
    query = db.query(Department).filter(
        Department.organization_id == current_org.id,
        Department.is_deleted == False
    )
    
    if is_active is not None:
        query = query.filter(Department.is_active == is_active)
        
    if parent_department_id is not None:
        query = query.filter(Department.parent_department_id == parent_department_id)
        
    if search:
        search_term = f"%{search}%"
        query = query.filter(Department.department_name.ilike(search_term))
        
    # Advanced Sorting Logic
    allowed_sort_fields = {
        "id": Department.id,
        "department_code": Department.department_code,
        "department_name": Department.department_name,
        "is_active": Department.is_active,
        "Recent": Department.created_at,
        "Oldest": Department.created_at
    }

    # Handle special case for legacy 'Oldest' sort_by string
    actual_sort_order = sort_order
    if sort_by == 'Oldest':
        actual_sort_order = 'asc'
    elif sort_by == 'Recent' or not sort_by:
        sort_by = 'Recent'
        if not sort_order or sort_order == 'asc': # If no specific order requested for 'Recent', default desc
             actual_sort_order = 'desc'

    if sort_by in allowed_sort_fields:
        sort_attr = allowed_sort_fields[sort_by]
        if actual_sort_order == "desc":
            query = query.order_by(sort_attr.desc())
        else:
            query = query.order_by(sort_attr.asc())
    else:
        # Fallback default
        query = query.order_by(Department.created_at.desc())
        
    total_records = query.count()
    
    pagination_data = None
    if page is not None:
        total_pages = (total_records + limit - 1) // limit
        skip = (page - 1) * limit
        departments = query.offset(skip).limit(limit).all()
        pagination_data = {
            "total_records": total_records,
            "current_page": page,
            "total_pages": total_pages,
            "page_size": limit
        }
    else:
        departments = query.all()
        pagination_data = {
            "total_records": total_records,
            "current_page": 1,
            "total_pages": 1,
            "page_size": total_records if total_records > 0 else 0
        }
    
    if not departments:
        return DepartmentListResponse(
            success=False,
            message="No departments found"
        )
    
    return DepartmentListResponse(
        success=True,
        message="Departments retrieved successfully",
        data=departments,
        pagination=pagination_data
    )

@router.post("/", response_model=DepartmentResponse, dependencies=[Depends(deps.check_permission(DepartmentPermissions.CREATE))])
def create_department(
    department_in: DepartmentCreate,
    db: Session = Depends(deps.get_db),
    current_org: Organization = Depends(deps.get_current_org)
):
    """
    Create a new department.
    """
    # Check if department with same code exists in the organization
    existing_dept = db.query(Department).filter(
        Department.organization_id == current_org.id,
        Department.department_code == department_in.department_code
    ).first()
    
    if existing_dept:
        raise HTTPException(
            status_code=400,
            detail=f"Department with code '{department_in.department_code}' already exists."
        )
    
    # Resolve UUIDs to IDs
    parent_dept_id = None
    if department_in.parent_department_uuid:
        parent_dept = db.query(Department).filter(
            Department.uuid == department_in.parent_department_uuid,
            Department.organization_id == current_org.id,
            Department.is_deleted == False
        ).first()
        if not parent_dept:
            raise HTTPException(
                status_code=400,
                detail=f"Parent department with uuid '{department_in.parent_department_uuid}' not found."
            )
        parent_dept_id = parent_dept.id

    head_of_dept_id = None
    if department_in.head_of_department_uuid:
        head_emp = db.query(Employee).filter(
            Employee.uuid == department_in.head_of_department_uuid,
            Employee.organization_id == current_org.id,
            Employee.is_deleted == False
        ).first()
        if not head_emp:
            raise HTTPException(
                status_code=400,
                detail=f"Head of department with uuid '{department_in.head_of_department_uuid}' not found."
            )
        head_of_dept_id = head_emp.id

    # Create new department
    dept_data = department_in.model_dump(exclude={'parent_department_uuid', 'head_of_department_uuid'})
    dept_data['parent_department_id'] = parent_dept_id
    dept_data['head_of_department_id'] = head_of_dept_id
    
    db_obj = Department(
        **dept_data,
        organization_id=current_org.id
    )
    db.add(db_obj)
    try:
        db.commit()
        db.refresh(db_obj)
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e))
        
    return DepartmentResponse(
        success=True,
        message="Department created successfully",
        data=db_obj
    )

@router.get("/hierarchy", response_model=DepartmentHierarchyListResponse, dependencies=[Depends(deps.check_permission(DepartmentPermissions.READ))])
def get_department_hierarchy(
    db: Session = Depends(deps.get_db),
    current_org: Organization = Depends(deps.get_current_org)
):
    """
    Get department hierarchy tree.
    """
    departments = db.query(Department).filter(
        Department.organization_id == current_org.id,
        Department.is_deleted == False
    ).all()
    
    # Convert to Pydantic models first to be mutable
    dept_map = {}
    for dept in departments:
        # We use .model_validate to ensure properties like uuid are loaded
        dept_schema = DepartmentHierarchySchema.model_validate(dept)
        dept_schema.sub_departments = [] # Ensure empty list init
        dept_map[dept.id] = dept_schema
        
    roots = []
    for dept in departments:
        current_node = dept_map[dept.id]
        if dept.parent_department_id and dept.parent_department_id in dept_map:
            parent_node = dept_map[dept.parent_department_id]
            parent_node.sub_departments.append(current_node)
        else:
            roots.append(current_node)
            
    return DepartmentHierarchyListResponse(
        success=True,
        message="Department hierarchy retrieved successfully",
        data=roots
    )

@router.get("/{department_uuid}", response_model=DepartmentDetailResponse, dependencies=[Depends(deps.check_permission(DepartmentPermissions.READ))])
def get_department(
    department_uuid: uuid.UUID,
    db: Session = Depends(deps.get_db),
    current_org: Organization = Depends(deps.get_current_org)
):
    """
    Get department details with employee count.
    """
    department = db.query(Department).filter(
        Department.uuid == department_uuid,
        Department.organization_id == current_org.id,
        Department.is_deleted == False
    ).first()
    
    if not department:
        # Based on previous preference for 200 OK with success=False for "Not Found" in lists,
        # but for single item retrieval by ID, 404 is semantically correct.
        # However, to be consistent with "success: false" JSON pattern:
        raise HTTPException(status_code=404, detail="Department not found")
        # Or return success=False if we change response model to allow Optional[data].
        # Let's stick to standard 404 for specific resource not found unless requested otherwise.
    
    # Count employees in this department
    employee_count = db.query(Employee).filter(
        Employee.department_id == department.id,
        Employee.is_deleted == False
    ).count()
    
    # Manually construct response data with employee count
    # Pydantic v2 .model_dump() on ORM object -> verify compatibility
    # Or just construct schema
    # DepartmentDetailSchema.from_orm(department) # Pydantic v1
    # DepartmentDetailSchema.model_validate(department) # Pydantic v2
    
    dept_data = DepartmentDetailSchema.model_validate(department)
    dept_data.employee_count = employee_count
    
    return DepartmentDetailResponse(
        success=True,
        message="Department retrieved successfully",
        data=dept_data
    )

@router.get("/{department_uuid}/employees", response_model=EmployeeListResponse, dependencies=[Depends(deps.check_permission(DepartmentPermissions.READ))])
def get_department_employees(
    department_uuid: uuid.UUID,
    page: Optional[int] = Query(None, ge=1, description="Page number"),
    limit: int = Query(10, ge=1, description="Items per page"),
    db: Session = Depends(deps.get_db),
    current_org: Organization = Depends(deps.get_current_org)
):
    """
    Get all employees in a department.
    """
    print(department_uuid)
    print(current_org.id)
    department = db.query(Department).filter(
        Department.uuid == department_uuid,
        Department.organization_id == current_org.id,
        Department.is_deleted == False
    ).first()
    
    if not department:
        raise HTTPException(status_code=404, detail="Department not found")
        
    query = db.query(Employee).filter(
        Employee.department_id == department.id,
        Employee.organization_id == current_org.id,
        Employee.is_deleted == False
    )
    
    total_records = query.count()
    
    pagination_data = None
    if page is not None:
        total_pages = (total_records + limit - 1) // limit
        skip = (page - 1) * limit
        employees = query.offset(skip).limit(limit).all()
        pagination_data = {
            "total_records": total_records,
            "current_page": page,
            "total_pages": total_pages,
            "page_size": limit
        }
    else:
        employees = query.all()
        pagination_data = {
            "total_records": total_records,
            "current_page": 1,
            "total_pages": 1,
            "page_size": total_records if total_records > 0 else 0
        }
        
    if not employees:
        return EmployeeListResponse(
            success=False,
            message="No employees found"
        )

    return EmployeeListResponse(
        success=True,
        message="Employees retrieved successfully",
        data=employees,
        pagination=pagination_data
    )

@router.put("/{department_uuid}", response_model=DepartmentResponse, dependencies=[Depends(deps.check_permission(DepartmentPermissions.UPDATE))])
def update_department(
    department_uuid: uuid.UUID,
    department_in: DepartmentUpdate,
    db: Session = Depends(deps.get_db),
    current_org: Organization = Depends(deps.get_current_org)
):
    """
    Update a department.
    """
    department = db.query(Department).filter(
        Department.uuid == department_uuid,
        Department.organization_id == current_org.id,
        Department.is_deleted == False
    ).first()
    
    if not department:
        raise HTTPException(status_code=404, detail="Department not found")
    
    # Check duplicate code if being updated
    if department_in.department_code and department_in.department_code != department.department_code:
        existing_dept = db.query(Department).filter(
            Department.organization_id == current_org.id,
            Department.department_code == department_in.department_code
        ).first()
        if existing_dept:
            raise HTTPException(
                status_code=400,
                detail=f"Department with code '{department_in.department_code}' already exists."
            )
            
    update_data = department_in.model_dump(exclude_unset=True, exclude={'parent_department_uuid', 'head_of_department_uuid'})
    
    # Handle Parent Department UUID update
    if department_in.parent_department_uuid is not None:
        parent_dept = db.query(Department).filter(
            Department.uuid == department_in.parent_department_uuid,
            Department.organization_id == current_org.id,
            Department.is_deleted == False
        ).first()
        
        if not parent_dept:
            raise HTTPException(
                status_code=400,
                detail=f"Parent department with uuid '{department_in.parent_department_uuid}' not found."
            )
            
        if parent_dept.id == department.id:
             raise HTTPException(status_code=400, detail="Cannot set department as its own parent")
             
        update_data['parent_department_id'] = parent_dept.id

    # Handle Head of Department UUID update
    if department_in.head_of_department_uuid is not None:
        head_emp = db.query(Employee).filter(
            Employee.uuid == department_in.head_of_department_uuid,
            Employee.organization_id == current_org.id,
            Employee.is_deleted == False
        ).first()
        
        if not head_emp:
             raise HTTPException(
                status_code=400,
                detail=f"Head of department with uuid '{department_in.head_of_department_uuid}' not found."
            )
        update_data['head_of_department_id'] = head_emp.id

    for field, value in update_data.items():
        setattr(department, field, value)
        
    db.add(department)
    try:
        db.commit()
        db.refresh(department)
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e))
        
    return DepartmentResponse(
        success=True,
        message="Department updated successfully",
        data=department
    )

@router.delete("/{department_uuid}", response_model=DepartmentDeleteResponse, dependencies=[Depends(deps.check_permission(DepartmentPermissions.DELETE))])
def delete_department(
    department_uuid: uuid.UUID,
    db: Session = Depends(deps.get_db),
    current_org: Organization = Depends(deps.get_current_org)
):
    """
    Delete a department.
    """
    department = db.query(Department).filter(
        Department.uuid == department_uuid,
        Department.organization_id == current_org.id,
        Department.is_deleted == False
    ).first()
    
    if not department:
        raise HTTPException(status_code=404, detail="Department not found")
        
    # Check for dependencies
    # 1. Active Employees
    active_employees = db.query(Employee).filter(
        Employee.department_id == department.id,
        Employee.is_deleted == False
    ).count()
    
    if active_employees > 0:
        raise HTTPException(
            status_code=400,
            detail=f"Cannot delete department. There are {active_employees} active employees assigned to it."
        )
        
    # 2. Sub-departments
    sub_departments = db.query(Department).filter(
        Department.parent_department_id == department.id
    ).count()
    
    if sub_departments > 0:
        raise HTTPException(
            status_code=400,
            detail=f"Cannot delete department. It has {sub_departments} sub-departments."
        )
        
    # Perform soft delete
    try:
        department.is_deleted = True
        department.deleted_at = datetime.utcnow()
        db.add(department)
        db.commit()
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e))
        
    return DepartmentDeleteResponse(
        success=True,
        message="Department deleted successfully",
        data=None
    )


