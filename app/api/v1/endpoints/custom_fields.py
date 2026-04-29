from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from app.api import deps
from app.models.employee import CustomFieldDefinition
from app.schemas.custom_field import (
    CustomFieldSchema,
    CustomFieldCreate,
    CustomFieldUpdate,
    CustomFieldResponse,
    CustomFieldListResponse,
    CustomFieldDetailResponse,
    CustomFieldDeleteResponse
)
from app.models.organization import Organization
from datetime import datetime
import uuid

router = APIRouter()

@router.get("/", response_model=CustomFieldListResponse)
def list_custom_fields(
    db: Session = Depends(deps.get_db),
    current_org: Organization = Depends(deps.get_current_org),
    is_active: Optional[bool] = Query(None, description="Filter by active status"),
    page: Optional[int] = Query(None, ge=1, description="Page number"),
    limit: int = Query(10, ge=1, description="Items per page"),
    sort_by: Optional[str] = Query(None, description="Sort by 'Recent' or 'Oldest'"),
):
    """
    List all custom field definitions.
    """
    query = db.query(CustomFieldDefinition).filter(
        CustomFieldDefinition.organization_id == current_org.id,
        CustomFieldDefinition.is_deleted == False
    )
    
    if is_active is not None:
        query = query.filter(CustomFieldDefinition.is_active == is_active)
        
    if sort_by == 'Recent':
        query = query.order_by(CustomFieldDefinition.created_at.desc())
    elif sort_by == 'Oldest':
        query = query.order_by(CustomFieldDefinition.created_at.asc())
    else:
        query = query.order_by(CustomFieldDefinition.display_order.asc(), CustomFieldDefinition.created_at.desc())
        
    total_records = query.count()
    
    pagination_data = None
    if page is not None:
        total_pages = (total_records + limit - 1) // limit
        skip = (page - 1) * limit
        fields = query.offset(skip).limit(limit).all()
        pagination_data = {
            "total_records": total_records,
            "current_page": page,
            "total_pages": total_pages,
            "page_size": limit
        }
    else:
        fields = query.all()
        pagination_data = {
            "total_records": total_records,
            "current_page": 1,
            "total_pages": 1,
            "page_size": total_records if total_records > 0 else 0
        }
        
    if not fields:
        return CustomFieldListResponse(
            success=False,
            message="No custom fields found"
        )
        
    return CustomFieldListResponse(
        success=True,
        message="Custom fields retrieved successfully",
        data=fields,
        pagination=pagination_data
    )

@router.post("/", response_model=CustomFieldResponse)
def create_custom_field(
    field_in: CustomFieldCreate,
    db: Session = Depends(deps.get_db),
    current_org: Organization = Depends(deps.get_current_org)
):
    """
    Create a new custom field definition.
    """
    # Check duplicate field name
    existing_field = db.query(CustomFieldDefinition).filter(
        CustomFieldDefinition.organization_id == current_org.id,
        CustomFieldDefinition.field_name == field_in.field_name
    ).first()
    
    if existing_field:
        raise HTTPException(
            status_code=400,
            detail=f"Custom field with name '{field_in.field_name}' already exists."
        )
        
    db_obj = CustomFieldDefinition(
        **field_in.model_dump(),
        organization_id=current_org.id
    )
    db.add(db_obj)
    try:
        db.commit()
        db.refresh(db_obj)
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e))
        
    return CustomFieldResponse(
        success=True,
        message="Custom field created successfully",
        data=db_obj
    )

@router.get("/{field_uuid}", response_model=CustomFieldDetailResponse)
def get_custom_field(
    field_uuid: uuid.UUID,
    db: Session = Depends(deps.get_db),
    current_org: Organization = Depends(deps.get_current_org)
):
    """
    Get custom field details.
    """
    custom_field = db.query(CustomFieldDefinition).filter(
        CustomFieldDefinition.uuid == field_uuid,
        CustomFieldDefinition.organization_id == current_org.id,
        CustomFieldDefinition.is_deleted == False
    ).first()
    
    if not custom_field:
        raise HTTPException(status_code=404, detail="Custom field not found")
        
    return CustomFieldDetailResponse(
        success=True,
        message="Custom field retrieved successfully",
        data=custom_field
    )

@router.put("/{field_uuid}", response_model=CustomFieldResponse)
def update_custom_field(
    field_uuid: uuid.UUID,
    field_in: CustomFieldUpdate,
    db: Session = Depends(deps.get_db),
    current_org: Organization = Depends(deps.get_current_org)
):
    """
    Update a custom field definition.
    """
    custom_field = db.query(CustomFieldDefinition).filter(
        CustomFieldDefinition.uuid == field_uuid,
        CustomFieldDefinition.organization_id == current_org.id,
        CustomFieldDefinition.is_deleted == False
    ).first()
    
    if not custom_field:
        raise HTTPException(status_code=404, detail="Custom field not found")
        
    update_data = field_in.model_dump(exclude_unset=True)
    
    for field, value in update_data.items():
        setattr(custom_field, field, value)
        
    db.add(custom_field)
    try:
        db.commit()
        db.refresh(custom_field)
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e))
        
    return CustomFieldResponse(
        success=True,
        message="Custom field updated successfully",
        data=custom_field
    )

@router.delete("/{field_uuid}", response_model=CustomFieldDeleteResponse)
def delete_custom_field(
    field_uuid: uuid.UUID,
    db: Session = Depends(deps.get_db),
    current_org: Organization = Depends(deps.get_current_org)
):
    """
    Delete a custom field definition (soft delete).
    """
    custom_field = db.query(CustomFieldDefinition).filter(
        CustomFieldDefinition.uuid == field_uuid,
        CustomFieldDefinition.organization_id == current_org.id,
        CustomFieldDefinition.is_deleted == False
    ).first()
    
    if not custom_field:
        raise HTTPException(status_code=404, detail="Custom field not found")
        
    # TODO: Check if values exist for this field in Employee Custom Fields?
    # For now, just soft delete the definition. 
    # Existing values in employees' JSON will remain but become 'orphaned' or 'historical'.
    
    # Perform soft delete
    try:
        custom_field.is_deleted = True
        custom_field.deleted_at = datetime.utcnow()
        db.add(custom_field)
        db.commit()
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e))
        
    return CustomFieldDeleteResponse(
        success=True,
        message="Custom field deleted successfully",
        data=None
    )
