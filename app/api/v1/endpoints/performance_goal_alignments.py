from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from sqlalchemy import or_
from typing import List, Optional, Union
import uuid
from datetime import datetime

from app.api import deps
from app.models.organization import Organization
from app.models.employee import Employee
from app.models.performance import (
    GoalAlignment, GoalType, OrganizationGoal, DepartmentGoal, EmployeeGoal
)
from app.schemas import performance_goal_alignments as schema
import math

class PerformancePermissions:
    READ = "205"
    CREATE = "206"
    UPDATE = "207"
    DELETE = "208"

router = APIRouter()

def _get_org_id(current_user: Union[Organization, Employee]) -> int:
    return current_user.id if isinstance(current_user, Organization) else current_user.organization_id

def _get_id_by_uuid(g_type: GoalType, g_uuid: uuid.UUID, db: Session) -> Optional[int]:
    if g_type == GoalType.ORGANIZATION:
        g = db.query(OrganizationGoal).filter(OrganizationGoal.uuid == g_uuid).first()
        return g.id if g else None
    elif g_type == GoalType.DEPARTMENT:
        g = db.query(DepartmentGoal).filter(DepartmentGoal.uuid == g_uuid).first()
        return g.id if g else None
    else:
        g = db.query(EmployeeGoal).filter(EmployeeGoal.uuid == g_uuid).first()
        return g.id if g else None

def _get_title_and_uuid(g_type: GoalType, g_id: int, db: Session):
    if g_type == GoalType.ORGANIZATION:
        g = db.query(OrganizationGoal).filter(OrganizationGoal.id == g_id).first()
        return (g.title if g else "Unknown Org Goal", g.uuid if g else None)
    elif g_type == GoalType.DEPARTMENT:
        g = db.query(DepartmentGoal).filter(DepartmentGoal.id == g_id).first()
        return (g.title if g else "Unknown Dept Goal", g.uuid if g else None)
    else:
        g = db.query(EmployeeGoal).filter(EmployeeGoal.id == g_id).first()
        return (g.title if g else "Unknown Employee Goal", g.uuid if g else None)

@router.get("/lookup", response_model=schema.GoalAlignmentListResponse)
def lookup_goal_alignments(
    page: int = Query(1, ge=1),
    limit: int = Query(10, ge=1, le=100),
    parent_goal_type: Optional[GoalType] = None,
    parent_goal_uuid: Optional[uuid.UUID] = None,
    child_goal_type: Optional[GoalType] = None,
    child_goal_uuid: Optional[uuid.UUID] = None,
    search: Optional[str] = Query(None),
    sort_by: Optional[str] = Query(None),
    sort_order: Optional[str] = Query('asc'),
    db: Session = Depends(deps.get_db),
    current_user: Union[Organization, Employee] = Depends(deps.get_current_user)
):
    org_id = _get_org_id(current_user)

    query = db.query(GoalAlignment).filter(GoalAlignment.organization_id == org_id)

    # Resolve parent uuid to parent id
    parent_goal_id = None
    if parent_goal_uuid:
        found_id = None
        if parent_goal_type:
            found_id = _get_id_by_uuid(parent_goal_type, parent_goal_uuid, db)
        else:
            for t in GoalType:
                found_id = _get_id_by_uuid(t, parent_goal_uuid, db)
                if found_id:
                    parent_goal_type = t
                    break
        parent_goal_id = found_id if found_id else -1

    # Resolve child uuid to child id
    child_goal_id = None
    if child_goal_uuid:
        found_id = None
        if child_goal_type:
            found_id = _get_id_by_uuid(child_goal_type, child_goal_uuid, db)
        else:
            for t in GoalType:
                found_id = _get_id_by_uuid(t, child_goal_uuid, db)
                if found_id:
                    child_goal_type = t
                    break
        child_goal_id = found_id if found_id else -1

    if parent_goal_type:
        query = query.filter(GoalAlignment.parent_goal_type == parent_goal_type)
    if parent_goal_id is not None:
        query = query.filter(GoalAlignment.parent_goal_id == parent_goal_id)

    if child_goal_type:
        query = query.filter(GoalAlignment.child_goal_type == child_goal_type)
    if child_goal_id is not None:
        query = query.filter(GoalAlignment.child_goal_id == child_goal_id)

    alignments = query.all()

    result_data = []
    for al in alignments:
        al_dict = al.__dict__.copy()
        p_title, p_uuid = _get_title_and_uuid(al.parent_goal_type, al.parent_goal_id, db)
        c_title, c_uuid = _get_title_and_uuid(al.child_goal_type, al.child_goal_id, db)
        al_dict['parent_goal_title'] = p_title
        al_dict['parent_goal_uuid'] = p_uuid
        al_dict['child_goal_title'] = c_title
        al_dict['child_goal_uuid'] = c_uuid
        result_data.append(al_dict)

    # In-memory Search
    if search:
        search_lower = search.lower()
        result_data = [
            al for al in result_data
            if (search_lower in (al.get('parent_goal_title') or '').lower() or
                search_lower in (al.get('child_goal_title') or '').lower() or
                search_lower in (al.get('notes') or '').lower())
        ]

    # In-memory Sorting
    actual_sort_order = sort_order
    if sort_by == 'Oldest':
        actual_sort_order = 'asc'
        sort_by = 'id'
    elif sort_by == 'Recent' or not sort_by:
        sort_by = 'id'
        if not sort_order or sort_order == 'asc':
            actual_sort_order = 'desc'

    reverse = (actual_sort_order == 'desc')

    if sort_by in ('id', 'created_at'):
        result_data.sort(key=lambda x: x.get('id', 0), reverse=reverse)
    elif sort_by in ('alignment_weight', 'weight'):
        result_data.sort(key=lambda x: float(x.get('alignment_weight') or 0), reverse=reverse)
    elif sort_by in ('parent_goal', 'parent_goal_title'):
        result_data.sort(key=lambda x: (x.get('parent_goal_title') or '').lower(), reverse=reverse)
    elif sort_by in ('child_goal', 'child_goal_title'):
        result_data.sort(key=lambda x: (x.get('child_goal_title') or '').lower(), reverse=reverse)
    else:
        # Fallback sort by id desc
        result_data.sort(key=lambda x: x.get('id', 0), reverse=True)

    total_records = len(result_data)
    total_pages = math.ceil(total_records / limit) if limit > 0 else 1
    skip = (page - 1) * limit
    paginated_data = result_data[skip : skip + limit]

    return {
        "success": True,
        "message": "Goal alignments fetched successfully",
        "data": paginated_data,
        "pagination": {
            "current_page": page,
            "total_pages": total_pages,
            "total_records": total_records,
            "limit": limit
        }
    }

@router.get("", response_model=schema.GoalAlignmentListResponse)
def list_goal_alignments(
    page: int = Query(1, ge=1),
    limit: int = Query(10, ge=1, le=100),
    parent_goal_type: Optional[GoalType] = None,
    parent_goal_uuid: Optional[uuid.UUID] = None,
    child_goal_type: Optional[GoalType] = None,
    child_goal_uuid: Optional[uuid.UUID] = None,
    search: Optional[str] = Query(None),
    sort_by: Optional[str] = Query(None),
    sort_order: Optional[str] = Query('asc'),
    db: Session = Depends(deps.get_db),
    current_user: Union[Organization, Employee] = Depends(deps.get_current_user)
):
    org_id = _get_org_id(current_user)
    if not isinstance(current_user, Organization):
        if not deps.has_permission(db, current_user, PerformancePermissions.READ):
            raise HTTPException(status_code=403, detail="Not authorized to view goal alignments")

    query = db.query(GoalAlignment).filter(GoalAlignment.organization_id == org_id)

    # Resolve parent uuid to parent id
    parent_goal_id = None
    if parent_goal_uuid:
        found_id = None
        if parent_goal_type:
            found_id = _get_id_by_uuid(parent_goal_type, parent_goal_uuid, db)
        else:
            for t in GoalType:
                found_id = _get_id_by_uuid(t, parent_goal_uuid, db)
                if found_id:
                    parent_goal_type = t
                    break
        parent_goal_id = found_id if found_id else -1

    # Resolve child uuid to child id
    child_goal_id = None
    if child_goal_uuid:
        found_id = None
        if child_goal_type:
            found_id = _get_id_by_uuid(child_goal_type, child_goal_uuid, db)
        else:
            for t in GoalType:
                found_id = _get_id_by_uuid(t, child_goal_uuid, db)
                if found_id:
                    child_goal_type = t
                    break
        child_goal_id = found_id if found_id else -1

    if parent_goal_type:
        query = query.filter(GoalAlignment.parent_goal_type == parent_goal_type)
    if parent_goal_id is not None:
        query = query.filter(GoalAlignment.parent_goal_id == parent_goal_id)

    if child_goal_type:
        query = query.filter(GoalAlignment.child_goal_type == child_goal_type)
    if child_goal_id is not None:
        query = query.filter(GoalAlignment.child_goal_id == child_goal_id)

    alignments = query.all()

    result_data = []
    for al in alignments:
        al_dict = al.__dict__.copy()
        p_title, p_uuid = _get_title_and_uuid(al.parent_goal_type, al.parent_goal_id, db)
        c_title, c_uuid = _get_title_and_uuid(al.child_goal_type, al.child_goal_id, db)
        al_dict['parent_goal_title'] = p_title
        al_dict['parent_goal_uuid'] = p_uuid
        al_dict['child_goal_title'] = c_title
        al_dict['child_goal_uuid'] = c_uuid
        result_data.append(al_dict)

    # In-memory Search
    if search:
        search_lower = search.lower()
        result_data = [
            al for al in result_data
            if (search_lower in (al.get('parent_goal_title') or '').lower() or
                search_lower in (al.get('child_goal_title') or '').lower() or
                search_lower in (al.get('notes') or '').lower())
        ]

    # In-memory Sorting
    actual_sort_order = sort_order
    if sort_by == 'Oldest':
        actual_sort_order = 'asc'
        sort_by = 'id'
    elif sort_by == 'Recent' or not sort_by:
        sort_by = 'id'
        if not sort_order or sort_order == 'asc':
            actual_sort_order = 'desc'

    reverse = (actual_sort_order == 'desc')

    if sort_by in ('id', 'created_at'):
        result_data.sort(key=lambda x: x.get('id', 0), reverse=reverse)
    elif sort_by in ('alignment_weight', 'weight'):
        result_data.sort(key=lambda x: float(x.get('alignment_weight') or 0), reverse=reverse)
    elif sort_by in ('parent_goal', 'parent_goal_title'):
        result_data.sort(key=lambda x: (x.get('parent_goal_title') or '').lower(), reverse=reverse)
    elif sort_by in ('child_goal', 'child_goal_title'):
        result_data.sort(key=lambda x: (x.get('child_goal_title') or '').lower(), reverse=reverse)
    else:
        # Fallback sort by id desc
        result_data.sort(key=lambda x: x.get('id', 0), reverse=True)

    total_records = len(result_data)
    total_pages = math.ceil(total_records / limit) if limit > 0 else 1
    skip = (page - 1) * limit
    paginated_data = result_data[skip : skip + limit]

    return {
        "success": True,
        "message": "Goal alignments fetched successfully",
        "data": paginated_data,
        "pagination": {
            "current_page": page,
            "total_pages": total_pages,
            "total_records": total_records,
            "limit": limit
        }
    }

@router.post("", response_model=schema.GoalAlignmentResponse)
def create_goal_alignment(
    payload: schema.GoalAlignmentCreate,
    db: Session = Depends(deps.get_db),
    current_user: Union[Organization, Employee] = Depends(deps.get_current_user)
):
    org_id = _get_org_id(current_user)
    if not isinstance(current_user, Organization):
        if not deps.has_permission(db, current_user, PerformancePermissions.UPDATE):
            raise HTTPException(status_code=403, detail="Not authorized to manage goal alignments")

    # Resolve parent_goal_uuid to parent_goal_id
    parent_goal_id = _get_id_by_uuid(payload.parent_goal_type, payload.parent_goal_uuid, db)
    if not parent_goal_id:
        raise HTTPException(status_code=404, detail="Parent goal not found")

    # Resolve child_goal_uuid to child_goal_id
    child_goal_id = _get_id_by_uuid(payload.child_goal_type, payload.child_goal_uuid, db)
    if not child_goal_id:
        raise HTTPException(status_code=404, detail="Child goal not found")

    # Prevent self-linking or same type circular reference
    if payload.parent_goal_type == payload.child_goal_type and parent_goal_id == child_goal_id:
        raise HTTPException(status_code=400, detail="Cannot align a goal to itself")

    # Check if alignment already exists
    existing = db.query(GoalAlignment).filter(
        GoalAlignment.organization_id == org_id,
        GoalAlignment.child_goal_type == payload.child_goal_type,
        GoalAlignment.child_goal_id == child_goal_id,
        GoalAlignment.parent_goal_type == payload.parent_goal_type,
        GoalAlignment.parent_goal_id == parent_goal_id
    ).first()

    if existing:
        raise HTTPException(status_code=400, detail="Goal alignment already exists")

    creator_id = None
    if isinstance(current_user, Employee):
        creator_id = current_user.id
    else:
        # Fallback to the first employee in the organization if created by organization admin
        first_emp = db.query(Employee).filter(Employee.organization_id == org_id).first()
        if first_emp:
            creator_id = first_emp.id
        else:
            raise HTTPException(
                status_code=400, 
                detail="Organization has no employees to assign as alignment creator"
            )

    alignment = GoalAlignment(
        organization_id=org_id,
        parent_goal_type=payload.parent_goal_type,
        parent_goal_id=parent_goal_id,
        child_goal_type=payload.child_goal_type,
        child_goal_id=child_goal_id,
        alignment_weight=payload.alignment_weight,
        notes=payload.notes,
        created_by=creator_id
    )

    db.add(alignment)
    db.commit()
    db.refresh(alignment)

    parent_title, parent_uuid = _get_title_and_uuid(alignment.parent_goal_type, alignment.parent_goal_id, db)
    child_title, child_uuid = _get_title_and_uuid(alignment.child_goal_type, alignment.child_goal_id, db)

    res_dict = alignment.__dict__.copy()
    res_dict['parent_goal_uuid'] = parent_uuid
    res_dict['parent_goal_title'] = parent_title
    res_dict['child_goal_uuid'] = child_uuid
    res_dict['child_goal_title'] = child_title

    return schema.GoalAlignmentResponse(
        success=True,
        message="Goal alignment created successfully",
        data=res_dict
    )

@router.put("/{alignment_id}", response_model=schema.GoalAlignmentResponse)
def update_goal_alignment(
    alignment_id: int,
    payload: schema.GoalAlignmentUpdate,
    db: Session = Depends(deps.get_db),
    current_user: Union[Organization, Employee] = Depends(deps.get_current_user)
):
    org_id = _get_org_id(current_user)
    if not isinstance(current_user, Organization):
        if not deps.has_permission(db, current_user, PerformancePermissions.UPDATE):
            raise HTTPException(status_code=403, detail="Not authorized to update goal alignments")

    alignment = db.query(GoalAlignment).filter(
        GoalAlignment.id == alignment_id,
        GoalAlignment.organization_id == org_id
    ).first()

    if not alignment:
        raise HTTPException(status_code=404, detail="Goal alignment not found")

    if payload.alignment_weight is not None:
        alignment.alignment_weight = payload.alignment_weight
    if payload.notes is not None:
        alignment.notes = payload.notes

    db.commit()
    db.refresh(alignment)

    parent_title, parent_uuid = _get_title_and_uuid(alignment.parent_goal_type, alignment.parent_goal_id, db)
    child_title, child_uuid = _get_title_and_uuid(alignment.child_goal_type, alignment.child_goal_id, db)

    res_dict = alignment.__dict__.copy()
    res_dict['parent_goal_uuid'] = parent_uuid
    res_dict['parent_goal_title'] = parent_title
    res_dict['child_goal_uuid'] = child_uuid
    res_dict['child_goal_title'] = child_title

    return schema.GoalAlignmentResponse(
        success=True,
        message="Goal alignment updated successfully",
        data=res_dict
    )

@router.delete("/{alignment_id}")
def delete_goal_alignment(
    alignment_id: int,
    db: Session = Depends(deps.get_db),
    current_user: Union[Organization, Employee] = Depends(deps.get_current_user)
):
    org_id = _get_org_id(current_user)
    if not isinstance(current_user, Organization):
        if not deps.has_permission(db, current_user, PerformancePermissions.UPDATE):
            raise HTTPException(status_code=403, detail="Not authorized to delete goal alignments")

    alignment = db.query(GoalAlignment).filter(
        GoalAlignment.id == alignment_id,
        GoalAlignment.organization_id == org_id
    ).first()

    if not alignment:
        raise HTTPException(status_code=404, detail="Goal alignment not found")

    db.delete(alignment)
    db.commit()

    return {"success": True, "message": "Goal alignment deleted successfully"}

@router.get("/tree", response_model=schema.GoalTreeResponse)
def get_goal_alignment_tree(
    fiscal_year: Optional[str] = None,
    db: Session = Depends(deps.get_db),
    current_user: Union[Organization, Employee] = Depends(deps.get_current_user)
):
    """
    Returns the complete top-down organizational goal tree for a given fiscal year.
    Builds the tree using the explicit goal_alignments table.
    """
    org_id = _get_org_id(current_user)
    if not isinstance(current_user, Organization):
        if not deps.has_permission(db, current_user, PerformancePermissions.READ):
            raise HTTPException(status_code=403, detail="Not authorized to view goal alignments")

    # 1. Fetch all goals
    org_query = db.query(OrganizationGoal).filter(OrganizationGoal.organization_id == org_id)
    dept_query = db.query(DepartmentGoal).filter(DepartmentGoal.organization_id == org_id, DepartmentGoal.is_deleted == False)
    emp_query = db.query(EmployeeGoal).filter(EmployeeGoal.organization_id == org_id, EmployeeGoal.is_deleted == False)
    
    if fiscal_year:
        org_query = org_query.filter(OrganizationGoal.fiscal_year == fiscal_year)
        dept_query = dept_query.filter(DepartmentGoal.fiscal_year == fiscal_year)
        emp_query = emp_query.filter(EmployeeGoal.fiscal_year == fiscal_year)

    org_goals = org_query.all()
    dept_goals = dept_query.all()
    emp_goals = emp_query.all()

    # 2. Fetch all alignments
    alignments = db.query(GoalAlignment).filter(GoalAlignment.organization_id == org_id).all()

    # 3. Create quick lookup dictionaries for node mapping
    nodes_map = {}
    
    for g in org_goals:
        key = (GoalType.ORGANIZATION, g.id)
        nodes_map[key] = schema.GoalTreeNode(
            goal_id=g.id,
            goal_uuid=g.uuid,
            goal_type=GoalType.ORGANIZATION,
            title=g.title,
            progress_percentage=g.progress_percentage or 0,
            status=g.status,
            children=[]
        )
        
    for g in dept_goals:
        key = (GoalType.DEPARTMENT, g.id)
        nodes_map[key] = schema.GoalTreeNode(
            goal_id=g.id,
            goal_uuid=g.uuid,
            goal_type=GoalType.DEPARTMENT,
            title=g.title,
            progress_percentage=g.progress_percentage or 0,
            status=g.status,
            department_name=g.department.department_name if g.department else None,
            children=[]
        )
        
    for g in emp_goals:
        key = (GoalType.INDIVIDUAL, g.id)
        nodes_map[key] = schema.GoalTreeNode(
            goal_id=g.id,
            goal_uuid=g.uuid,
            goal_type=GoalType.INDIVIDUAL,
            title=g.title,
            progress_percentage=g.progress_percentage or 0,
            status=g.status,
            employee_name=f"{g.employee.first_name} {g.employee.last_name}" if g.employee else None,
            children=[]
        )

    # 4. Map children to parents
    # Any node that is a child is added to a set of 'has_parent'
    has_parent_keys = set()
    for al in alignments:
        parent_key = (al.parent_goal_type, al.parent_goal_id)
        child_key = (al.child_goal_type, al.child_goal_id)
        
        if parent_key in nodes_map and child_key in nodes_map:
            nodes_map[parent_key].children.append(nodes_map[child_key])
            has_parent_keys.add(child_key)

    # 5. Root nodes are nodes that don't have a parent in the explicit alignments table
    # Standard tree structure: root nodes are typically Organization Goals, but could be detached Dept/Emp goals.
    # To keep it clean, we return all roots.
    tree = []
    for key, node in nodes_map.items():
        if key not in has_parent_keys:
            tree.append(node)

    return schema.GoalTreeResponse(
        success=True,
        message="Goal tree fetched successfully",
        data=tree
    )
