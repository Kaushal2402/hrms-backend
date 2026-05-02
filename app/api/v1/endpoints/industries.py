import uuid
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.api import deps
from app.models.organization import Industry
from app.schemas.industry import IndustrySchema, IndustryCreate, IndustryUpdate, IndustryListResponse, IndustryResponse
from app.core.permissions import IndustryPermissions

router = APIRouter()

@router.get("/", response_model=IndustryListResponse)
def list_industries(
    db: Session = Depends(deps.get_db),
    skip: int = 0,
    limit: int = 100,
    active_only: bool = True
):
    """
    Retrieve all active industries. (Public endpoint for registration)
    """
    query = db.query(Industry)
    if active_only:
        query = query.filter(Industry.is_active == True)
    
    industries = query.offset(skip).limit(limit).all()
    
    return {
        "success": True,
        "message": "Industries retrieved successfully",
        "data": industries
    }

@router.post("/", response_model=IndustryResponse, dependencies=[Depends(deps.check_permission(IndustryPermissions.CREATE))])
def create_industry(
    industry_in: IndustryCreate,
    db: Session = Depends(deps.get_db)
):
    """
    Create a new industry. (Admin only)
    """
    db_industry = Industry(**industry_in.model_dump())
    db.add(db_industry)
    try:
        db.commit()
        db.refresh(db_industry)
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Industry with name '{industry_in.name}' already exists."
        )
    
    return {
        "success": True,
        "message": "Industry created successfully",
        "data": db_industry
    }

@router.get("/{industry_uuid}", response_model=IndustryResponse)
def get_industry(
    industry_uuid: uuid.UUID,
    db: Session = Depends(deps.get_db)
):
    """
    Get industry by UUID.
    """
    industry = db.query(Industry).filter(Industry.uuid == industry_uuid).first()
    if not industry:
        raise HTTPException(status_code=404, detail="Industry not found")
    
    return {
        "success": True,
        "message": "Industry retrieved successfully",
        "data": industry
    }

@router.put("/{industry_uuid}", response_model=IndustryResponse, dependencies=[Depends(deps.check_permission(IndustryPermissions.UPDATE))])
def update_industry(
    industry_uuid: uuid.UUID,
    industry_in: IndustryUpdate,
    db: Session = Depends(deps.get_db)
):
    """
    Update an industry. (Admin only)
    """
    industry = db.query(Industry).filter(Industry.uuid == industry_uuid).first()
    if not industry:
        raise HTTPException(status_code=404, detail="Industry not found")
    
    update_data = industry_in.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(industry, field, value)
    
    db.add(industry)
    db.commit()
    db.refresh(industry)
    
    return {
        "success": True,
        "message": "Industry updated successfully",
        "data": industry
    }

@router.delete("/{industry_uuid}", response_model=IndustryResponse, dependencies=[Depends(deps.check_permission(IndustryPermissions.DELETE))])
def delete_industry(
    industry_uuid: uuid.UUID,
    db: Session = Depends(deps.get_db)
):
    """
    Soft delete/Deactivate an industry. (Admin only)
    """
    industry = db.query(Industry).filter(Industry.uuid == industry_uuid).first()
    if not industry:
        raise HTTPException(status_code=404, detail="Industry not found")
    
    industry.is_active = False
    db.commit()
    
    return {
        "success": True,
        "message": "Industry deactivated successfully",
        "data": industry
    }
