import uuid
from datetime import date, datetime
from typing import List, Optional
from fastapi import APIRouter, Depends, Query, HTTPException, status
from sqlalchemy.orm import Session, aliased, joinedload
from sqlalchemy import and_, or_
from app.api import deps
from app.models.attendance import ApprovalDelegation
from app.models.employee import Employee
from app.models.organization import Organization
from app.schemas.attendance import (
    ApprovalDelegationListResponse, 
    ApprovalDelegationSchema,
    ApprovalDelegationCreate,
    ApprovalDelegationUpdate,
    ApprovalDelegationResponse
)

router = APIRouter()

def map_delegation_response(delegation: ApprovalDelegation, delegator_uuid: uuid.UUID = None, delegate_to_uuid: uuid.UUID = None) -> ApprovalDelegationSchema:
    """Helper to map ORM and resolved UUIDs to schema including employee objects."""
    result = ApprovalDelegationSchema.model_validate(delegation)
    
    # Ensure UUIDs are populated if provided (useful for create/update where we already have them)
    if delegator_uuid:
        result.delegator_uuid = delegator_uuid
    elif delegation.delegator:
        result.delegator_uuid = delegation.delegator.uuid
        
    if delegate_to_uuid:
        result.delegate_to_uuid = delegate_to_uuid
    elif delegation.delegate_to:
        result.delegate_to_uuid = delegation.delegate_to.uuid

    # Populate employee objects if relationships are loaded
    if delegation.delegator:
        from app.schemas.employee import EmployeeMinimalSchema
        result.delegator = EmployeeMinimalSchema.model_validate(delegation.delegator)
        result.delegator_name = f"{delegation.delegator.first_name} {delegation.delegator.last_name}"
        
    if delegation.delegate_to:
        from app.schemas.employee import EmployeeMinimalSchema
        result.delegate_to = EmployeeMinimalSchema.model_validate(delegation.delegate_to)
        result.delegate_to_name = f"{delegation.delegate_to.first_name} {delegation.delegate_to.last_name}"
        
    return result

@router.post("/", response_model=ApprovalDelegationResponse)
def create_approval_delegation(
    delegation_in: ApprovalDelegationCreate,
    db: Session = Depends(deps.get_db),
    current_org: Organization = Depends(deps.get_current_org)
):
    """
    Create a new approval delegation.
    Resolves delegator and delegate_to UUIDs to IDs.
    """
    # 1. Resolve Delegator
    delegator = db.query(Employee.id).filter(
        Employee.uuid == delegation_in.delegator_uuid,
        Employee.organization_id == current_org.id,
        Employee.is_deleted == False
    ).first()
    if not delegator:
        raise HTTPException(status_code=400, detail="Delegator not found")

    # 2. Resolve Delegate To
    delegatee = db.query(Employee.id).filter(
        Employee.uuid == delegation_in.delegate_to_uuid,
        Employee.organization_id == current_org.id,
        Employee.is_deleted == False
    ).first()
    if not delegatee:
        raise HTTPException(status_code=400, detail="Delegate target employee not found")

    # 3. Create record
    delegation_data = delegation_in.model_dump(exclude={'delegator_uuid', 'delegate_to_uuid'})
    delegation = ApprovalDelegation(
        **delegation_data,
        delegator_id=delegator[0],
        delegate_to_id=delegatee[0],
        organization_id=current_org.id
    )

    db.add(delegation)
    try:
        db.commit()
        # Refresh with joinedload to ensure relationships are loaded for response
        delegation = db.query(ApprovalDelegation).options(
            joinedload(ApprovalDelegation.delegator),
            joinedload(ApprovalDelegation.delegate_to)
        ).filter(ApprovalDelegation.id == delegation.id).first()
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create delegation: {str(e)}"
        )

    return ApprovalDelegationResponse(
        success=True,
        message="Approval delegation created successfully",
        data=map_delegation_response(delegation)
    )

@router.get("/", response_model=ApprovalDelegationListResponse)
def list_approval_delegations(
    db: Session = Depends(deps.get_db),
    current_org: Organization = Depends(deps.get_current_org),
    delegator_uuid: Optional[uuid.UUID] = Query(None, description="Filter by delegator UUID"),
    delegate_to_uuid: Optional[uuid.UUID] = Query(None, description="Filter by delegate recipient UUID"),
    is_active: Optional[bool] = Query(None, description="Filter by active status"),
    delegation_date: Optional[date] = Query(None, alias="date", description="Check active delegations on this date"),
    page: int = Query(1, ge=1, description="Page number"),
    limit: int = Query(10, ge=1, description="Items per page")
):
    """
    List approval delegations with filtering and pagination.
    """
    delegator_alias = aliased(Employee)
    delegatee_alias = aliased(Employee)

    query = db.query(ApprovalDelegation).options(
        joinedload(ApprovalDelegation.delegator),
        joinedload(ApprovalDelegation.delegate_to)
    ).join(
        delegator_alias, ApprovalDelegation.delegator_id == delegator_alias.id
    ).join(
        delegatee_alias, ApprovalDelegation.delegate_to_id == delegatee_alias.id
    ).filter(
        ApprovalDelegation.organization_id == current_org.id
    )

    if delegator_uuid:
        query = query.filter(delegator_alias.uuid == delegator_uuid)
    
    if delegate_to_uuid:
        query = query.filter(delegatee_alias.uuid == delegate_to_uuid)
    
    if is_active is not None:
        query = query.filter(ApprovalDelegation.is_active == is_active)
    
    if delegation_date:
        query = query.filter(
            and_(
                ApprovalDelegation.from_date <= delegation_date,
                ApprovalDelegation.to_date >= delegation_date
            )
        )

    # Sort by created_at desc
    query = query.order_by(ApprovalDelegation.created_at.desc())

    # Pagination
    total_records = query.count()
    total_pages = (total_records + limit - 1) // limit
    skip = (page - 1) * limit

    results = query.offset(skip).limit(limit).all()

    delegations = []
    for delegation in results:
        delegations.append(map_delegation_response(delegation))

    pagination = {
        "total_records": total_records,
        "current_page": page,
        "total_pages": total_pages,
        "page_size": limit
    }

    return ApprovalDelegationListResponse(
        success=True,
        message="Approval delegations retrieved successfully",
        data=delegations,
        pagination=pagination
    )

@router.get("/{delegation_id}", response_model=ApprovalDelegationResponse)
def get_approval_delegation(
    delegation_id: str,
    db: Session = Depends(deps.get_db),
    current_org: Organization = Depends(deps.get_current_org)
):
    """
    Get detailed information about a delegation.
    """
    delegation_row = None
    delegator_alias = aliased(Employee)
    delegatee_alias = aliased(Employee)
    
    base_query = db.query(ApprovalDelegation).options(
        joinedload(ApprovalDelegation.delegator),
        joinedload(ApprovalDelegation.delegate_to)
    ).filter(
        ApprovalDelegation.organization_id == current_org.id
    )

    try:
        uuid_obj = uuid.UUID(delegation_id)
        delegation = base_query.filter(ApprovalDelegation.uuid == uuid_obj).first()
    except ValueError:
        try:
            delegation = base_query.filter(ApprovalDelegation.id == int(delegation_id)).first()
        except ValueError:
            pass

    if not delegation:
        raise HTTPException(status_code=404, detail="Delegation not found")

    return ApprovalDelegationResponse(
        success=True,
        message="Delegation details retrieved successfully",
        data=map_delegation_response(delegation)
    )

@router.put("/{delegation_id}", response_model=ApprovalDelegationResponse)
def update_approval_delegation(
    delegation_id: str,
    delegation_in: ApprovalDelegationUpdate,
    db: Session = Depends(deps.get_db),
    current_org: Organization = Depends(deps.get_current_org)
):
    """
    Update an existing delegation.
    """
    # 1. Fetch delegation
    delegation = None
    try:
        uuid_obj = uuid.UUID(delegation_id)
        delegation = db.query(ApprovalDelegation).filter(
            ApprovalDelegation.uuid == uuid_obj,
            ApprovalDelegation.organization_id == current_org.id
        ).first()
    except ValueError:
        try:
            delegation = db.query(ApprovalDelegation).filter(
                ApprovalDelegation.id == int(delegation_id),
                ApprovalDelegation.organization_id == current_org.id
            ).first()
        except ValueError:
            pass

    if not delegation:
        raise HTTPException(status_code=404, detail="Delegation not found")

    # 2. Resolve target delegate if provided
    update_data = delegation_in.model_dump(exclude_unset=True, exclude={'delegate_to_uuid'})
    if delegation_in.delegate_to_uuid:
        delegatee = db.query(Employee.id).filter(
            Employee.uuid == delegation_in.delegate_to_uuid,
            Employee.organization_id == current_org.id,
            Employee.is_deleted == False
        ).first()
        if not delegatee:
            raise HTTPException(status_code=400, detail="Delegate target employee not found")
        update_data['delegate_to_id'] = delegatee[0]

    # 3. Apply updates
    for field, value in update_data.items():
        setattr(delegation, field, value)

    try:
        db.commit()
        # Refresh with joinedload to ensure relationships are loaded for response
        delegation = db.query(ApprovalDelegation).options(
            joinedload(ApprovalDelegation.delegator),
            joinedload(ApprovalDelegation.delegate_to)
        ).filter(ApprovalDelegation.id == delegation.id).first()
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update delegation: {str(e)}"
        )

    return ApprovalDelegationResponse(
        success=True,
        message="Delegation updated successfully",
        data=map_delegation_response(delegation)
    )

@router.delete("/{delegation_id}", response_model=dict)
def delete_approval_delegation(
    delegation_id: str,
    db: Session = Depends(deps.get_db),
    current_org: Organization = Depends(deps.get_current_org)
):
    """
    Hard delete a delegation (usually no soft-delete required for brief authority transfers).
    """
    delegation = None
    try:
        uuid_obj = uuid.UUID(delegation_id)
        delegation = db.query(ApprovalDelegation).filter(
            ApprovalDelegation.uuid == uuid_obj,
            ApprovalDelegation.organization_id == current_org.id
        ).first()
    except ValueError:
        try:
            delegation = db.query(ApprovalDelegation).filter(
                ApprovalDelegation.id == int(delegation_id),
                ApprovalDelegation.organization_id == current_org.id
            ).first()
        except ValueError:
            pass

    if not delegation:
        raise HTTPException(status_code=404, detail="Delegation not found")

    try:
        db.delete(delegation)
        db.commit()
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete delegation: {str(e)}"
        )

    return {
        "success": True,
        "message": "Delegation deleted successfully",
        "data": None
    }
