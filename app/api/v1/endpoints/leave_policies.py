from typing import List, Optional
import uuid
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session, joinedload
from fastapi.responses import JSONResponse
from datetime import datetime

from app.api import deps
from app.models.attendance import LeavePolicy, LeaveType, LeavePolicyMapping
from app.models.employee import Department, Location
from app.models.organization import Organization
from app.schemas.leave import LeavePolicyListResponse, LeavePolicyCreate, LeavePolicyResponse, LeavePolicyUpdate, LeavePolicySchema

router = APIRouter()

def populate_policy_uuids(policy: LeavePolicy, db: Session) -> LeavePolicySchema:
    """Helper to map department/location IDs back to UUIDs for the response."""
    result = LeavePolicySchema.model_validate(policy)
    
    if policy.department_ids:
        dept_uuids = db.query(Department.uuid).filter(
            Department.id.in_(policy.department_ids)
        ).all()
        result.department_uuids = [r[0] for r in dept_uuids]
        
    if policy.location_ids:
        loc_uuids = db.query(Location.uuid).filter(
            Location.id.in_(policy.location_ids)
        ).all()
        result.location_uuids = [r[0] for r in loc_uuids]
        
    return result

@router.get("/", response_model=LeavePolicyListResponse)
def list_leave_policies(
    db: Session = Depends(deps.get_db),
    current_org: Organization = Depends(deps.get_current_org),
    page: Optional[int] = Query(None, ge=1, description="Page number"),
    limit: int = Query(10, ge=1, description="Items per page"),
    is_active: Optional[bool] = Query(None, description="Filter by active status"),
    search: Optional[str] = Query(None, description="Search by policy name"),
    sort_by: str = Query("policy_name", description="Sort by policy_name, applicable_to, effective_from, is_active"),
    order: str = Query("asc", description="Sort order (asc, desc)"),
    authorized: bool = Depends(deps.check_permission("47"))
):
    """
    List all leave policies for the organization with pagination and filtering.
    """
    query = db.query(LeavePolicy).filter(
        LeavePolicy.organization_id == current_org.id,
        LeavePolicy.is_deleted == False
    )
    
    # Optional filtering
    if is_active is not None:
        query = query.filter(LeavePolicy.is_active == is_active)
        
    if search:
        search_term = f"%{search}%"
        query = query.filter(LeavePolicy.policy_name.ilike(search_term))
        
    # Sorting
    sort_map = {
        "policy_name": LeavePolicy.policy_name,
        "applicable_to": LeavePolicy.applicable_to,
        "effective_from": LeavePolicy.effective_from,
        "is_active": LeavePolicy.is_active
    }
    
    sort_column = sort_map.get(sort_by, LeavePolicy.policy_name)
    if order.lower() == "desc":
        query = query.order_by(sort_column.desc())
    else:
        query = query.order_by(sort_column.asc())
        
    # query = query.order_by(LeavePolicy.policy_name.asc())
    
    # Pagination
    total_records = query.count()
    
    pagination_data = None
    if page is not None:
        total_pages = (total_records + limit - 1) // limit
        skip = (page - 1) * limit
        policies = query.offset(skip).limit(limit).all()
        pagination_data = {
            "total_records": total_records,
            "current_page": page,
            "total_pages": total_pages,
            "page_size": limit
        }
    else:
        policies = query.all()
        pagination_data = {
            "total_records": total_records,
            "current_page": 1,
            "total_pages": 1,
            "page_size": total_records if total_records > 0 else 0
        }
        
    return LeavePolicyListResponse(
        success=True,
        message="Leave policies retrieved successfully",
        data=[populate_policy_uuids(policy, db) for policy in policies],
        pagination=pagination_data
    )

@router.post("/", response_model=LeavePolicyResponse)
def create_leave_policy(
    policy_in: LeavePolicyCreate,
    db: Session = Depends(deps.get_db),
    current_org: Organization = Depends(deps.get_current_org),
    authorized: bool = Depends(deps.check_permission("48"))
):
    """
    Create a new leave policy and its mappings.
    """
    # 1. Check for duplicate name
    existing = db.query(LeavePolicy).filter(
        LeavePolicy.organization_id == current_org.id,
        LeavePolicy.policy_name == policy_in.policy_name,
        LeavePolicy.is_deleted == False
    ).first()
    
    if existing:
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={"success": False, "message": "Policy with this name already exists", "data": None}
        )
        
    # 2. If is_default is true, unset other defaults
    if policy_in.is_default:
        db.query(LeavePolicy).filter(
            LeavePolicy.organization_id == current_org.id,
            LeavePolicy.is_default == True
        ).update({LeavePolicy.is_default: False})

    # 3. Resolve UUIDs to IDs
    policy_data = policy_in.dict(exclude={'mappings', 'department_uuids', 'location_uuids'})
    
    if policy_in.department_uuids:
        dept_ids = db.query(Department.id).filter(
            Department.uuid.in_(policy_in.department_uuids),
            Department.organization_id == current_org.id,
            Department.is_deleted == False
        ).all()
        policy_data['department_ids'] = [r[0] for r in dept_ids]

    if policy_in.location_uuids:
        loc_ids = db.query(Location.id).filter(
            Location.uuid.in_(policy_in.location_uuids),
            Location.organization_id == current_org.id,
            Location.is_deleted == False
        ).all()
        policy_data['location_ids'] = [r[0] for r in loc_ids]

    policy = LeavePolicy(**policy_data)
    policy.organization_id = current_org.id
    
    db.add(policy)
    db.flush() # Get policy id

    # 4. Create Mappings
    for mapping_in in policy_in.mappings:
        # Resolve leave type uuid to id
        leave_type = db.query(LeaveType).filter(
            LeaveType.uuid == mapping_in.leave_type_uuid,
            LeaveType.organization_id == current_org.id,
            LeaveType.is_deleted == False
        ).first()
        
        if not leave_type:
            db.rollback()
            return JSONResponse(
                status_code=status.HTTP_404_NOT_FOUND,
                content={"success": False, "message": f"Leave type with UUID {mapping_in.leave_type_uuid} not found", "data": None}
            )
            
        mapping = LeavePolicyMapping(
            leave_policy_id=policy.id,
            leave_type_id=leave_type.id,
            annual_quota=mapping_in.annual_quota,
            accrual_rate_override=mapping_in.accrual_rate_override,
            is_active=mapping_in.is_active,
            created_by=None # To be updated with current employee context if needed
        )
        db.add(mapping)
        
    db.commit()
    db.refresh(policy)

    # Reload with relationships for response
    policy = db.query(LeavePolicy).filter(LeavePolicy.id == policy.id).options(
        joinedload(LeavePolicy.mappings).joinedload(LeavePolicyMapping.leave_type)
    ).first()
    
    return LeavePolicyResponse(
        success=True,
        message="Leave policy created successfully",
        data=populate_policy_uuids(policy, db)
    )

@router.get("/{policy_uuid}", response_model=LeavePolicyResponse)
def get_leave_policy(
    policy_uuid: uuid.UUID,
    db: Session = Depends(deps.get_db),
    current_org: Organization = Depends(deps.get_current_org),
    authorized: bool = Depends(deps.check_permission("47"))
):
    """
    Get detailed information for a specific leave policy, including mappings.
    """
    policy = db.query(LeavePolicy).filter(
        LeavePolicy.uuid == policy_uuid,
        LeavePolicy.organization_id == current_org.id,
        LeavePolicy.is_deleted == False
    ).options(
        joinedload(LeavePolicy.mappings).joinedload(LeavePolicyMapping.leave_type)
    ).first()
    
    if not policy:
        return JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND,
            content={"success": False, "message": "Leave policy not found", "data": None}
        )
        
    return LeavePolicyResponse(
        success=True,
        message="Leave policy retrieved successfully",
        data=populate_policy_uuids(policy, db)
    )

@router.put("/{policy_uuid}", response_model=LeavePolicyResponse)
def update_leave_policy(
    policy_uuid: uuid.UUID,
    policy_in: LeavePolicyUpdate,
    db: Session = Depends(deps.get_db),
    current_org: Organization = Depends(deps.get_current_org),
    authorized: bool = Depends(deps.check_permission("49"))
):
    """
    Update an existing leave policy and its mappings.
    """
    policy = db.query(LeavePolicy).filter(
        LeavePolicy.uuid == policy_uuid,
        LeavePolicy.organization_id == current_org.id,
        LeavePolicy.is_deleted == False
    ).first()
    
    if not policy:
        return JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND,
            content={"success": False, "message": "Leave policy not found", "data": None}
        )
        
    # 1. Check for duplicate name if name is being changed
    if policy_in.policy_name and policy_in.policy_name != policy.policy_name:
        existing = db.query(LeavePolicy).filter(
            LeavePolicy.organization_id == current_org.id,
            LeavePolicy.policy_name == policy_in.policy_name,
            LeavePolicy.id != policy.id,
            LeavePolicy.is_deleted == False
        ).first()
        
        if existing:
            return JSONResponse(
                status_code=status.HTTP_400_BAD_REQUEST,
                content={"success": False, "message": "Policy with this name already exists", "data": None}
            )
            
    # 2. If is_default is true, unset other defaults
    if policy_in.is_default:
        db.query(LeavePolicy).filter(
            LeavePolicy.organization_id == current_org.id,
            LeavePolicy.is_default == True,
            LeavePolicy.id != policy.id
        ).update({LeavePolicy.is_default: False})

    # 3. Update Policy Header
    update_data = policy_in.dict(exclude={'mappings', 'department_uuids', 'location_uuids'}, exclude_unset=True)
    
    if policy_in.department_uuids is not None:
        dept_ids = db.query(Department.id).filter(
            Department.uuid.in_(policy_in.department_uuids),
            Department.organization_id == current_org.id,
            Department.is_deleted == False
        ).all()
        update_data['department_ids'] = [r[0] for r in dept_ids]

    if policy_in.location_uuids is not None:
        loc_ids = db.query(Location.id).filter(
            Location.uuid.in_(policy_in.location_uuids),
            Location.organization_id == current_org.id,
            Location.is_deleted == False
        ).all()
        update_data['location_ids'] = [r[0] for r in loc_ids]

    for field, value in update_data.items():
        setattr(policy, field, value)
        
    # 4. Update Mappings if provided
    if policy_in.mappings is not None:
        # Delete existing mappings
        db.query(LeavePolicyMapping).filter(LeavePolicyMapping.leave_policy_id == policy.id).delete()
        
        # Create new mappings
        for mapping_in in policy_in.mappings:
            leave_type = db.query(LeaveType).filter(
                LeaveType.uuid == mapping_in.leave_type_uuid,
                LeaveType.organization_id == current_org.id,
                LeaveType.is_deleted == False
            ).first()
            
            if not leave_type:
                db.rollback()
                return JSONResponse(
                    status_code=status.HTTP_404_NOT_FOUND,
                    content={"success": False, "message": f"Leave type with UUID {mapping_in.leave_type_uuid} not found", "data": None}
                )
                
            mapping = LeavePolicyMapping(
                leave_policy_id=policy.id,
                leave_type_id=leave_type.id,
                annual_quota=mapping_in.annual_quota,
                accrual_rate_override=mapping_in.accrual_rate_override,
                is_active=mapping_in.is_active,
                created_by=None
            )
            db.add(mapping)
            
    db.commit()
    db.refresh(policy)
    
    return LeavePolicyResponse(
        success=True,
        message="Leave policy updated successfully",
        data=policy
    )

@router.delete("/{policy_uuid}")
def delete_leave_policy(
    policy_uuid: uuid.UUID,
    db: Session = Depends(deps.get_db),
    current_org: Organization = Depends(deps.get_current_org),
    authorized: bool = Depends(deps.check_permission("50"))
):
    """
    Soft delete a leave policy.
    """
    policy = db.query(LeavePolicy).filter(
        LeavePolicy.uuid == policy_uuid,
        LeavePolicy.organization_id == current_org.id,
        LeavePolicy.is_deleted == False
    ).first()
    
    if not policy:
        return JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND,
            content={"success": False, "message": "Leave policy not found", "data": None}
        )
        
    policy.is_deleted = True
    policy.deleted_at = datetime.utcnow()
    policy.is_active = False # Deactivate on delete
    
    db.commit()
    
    return {
        "success": True, 
        "message": "Leave policy deleted successfully"
    }
