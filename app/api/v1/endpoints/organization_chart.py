from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session, joinedload
from typing import List, Optional, Dict
from app.api import deps
from app.models.employee import Employee
from app.models.organization import Organization
from app.schemas.employee import OrgChartResponse, OrgChartNode, EmployeeSummarySchema

router = APIRouter()

def build_hierarchy(employees: List[Employee], depth_level: Optional[int] = None) -> List[OrgChartNode]:
    # Map by ID
    emp_map: Dict[int, OrgChartNode] = {}
    roots: List[OrgChartNode] = []
    
    # First pass: create nodes
    for emp in employees:
        node = OrgChartNode(
            employee=EmployeeSummarySchema.model_validate(emp),
            children=[]
        )
        emp_map[emp.id] = node
        
    # Second pass: link children
    for emp in employees:
        node = emp_map[emp.id]
        if emp.reporting_manager_id and emp.reporting_manager_id in emp_map:
            parent = emp_map[emp.reporting_manager_id]
            parent.children.append(node)
        else:
            # No parent in the current set, so it's a root
            roots.append(node)
            
    # Apply depth level if needed (BFS/DFS traversal to prune)
    if depth_level is not None:
        def prune(nodes: List[OrgChartNode], current_depth: int):
            if current_depth >= depth_level:
                for n in nodes:
                    n.children = []
                return
            for n in nodes:
                prune(n.children, current_depth + 1)
        
        prune(roots, 1)

    return roots

@router.get("/", response_model=OrgChartResponse)
def get_organization_chart(
    department_id: Optional[int] = None,
    location_id: Optional[int] = None,
    depth_level: Optional[int] = None,
    db: Session = Depends(deps.get_db),
    current_org: Organization = Depends(deps.get_current_org)
):
    """
    Get hierarchy.
    If filters (department, location) are applied, we fetch employees matching criteria.
    Hierarchy is built based on 'reporting_manager_id'.
    Note: Filtering by department might break the tree if manager is in different department.
    Strategy: Fetch ALL active employees to build tree, then filter? Or fetch matching?
    Standard Org Chart usually shows everything, or subtree.
    If filtered, we might just show relevant nodes, but they might be disconnected.
    Better: Filter acts as "Start from these nodes (as roots) or just filter content?".
    Given typical request, let's fetch ALL active employees for consistency, then maybe filter roots?
    
    Revised Strategy:
    1. Fetch ALL active employees for Org (to ensure links are correct).
    2. Build full tree.
    3. If Department/Location filtered, maybe filter the output roots or highlight?
    User request implies "Query Params". Usually implies filtering the VIEW.
    If I filter DB query by department, I get a list of employees in that dept. Some might report to others in same list, some to others outside.
    Tree construction will make those reporting to outside as "Roots" (since parent not in map).
    This is often acceptable view for "Department Org Chart".
    
    So: Filter DB by criteria. Build tree from result.
    """
    query = db.query(Employee).options(
        joinedload(Employee.job_title),
        joinedload(Employee.department)
    ).filter(
        Employee.organization_id == current_org.id,
        Employee.is_active == True,
        Employee.employment_status == 'active' # Assuming basic active check
    )
    
    if department_id:
        query = query.filter(Employee.department_uuid == department_id)
    if location_id:
        query = query.filter(Employee.location_uuid == location_id)
        
    employees = query.all()
    
    hierarchy = build_hierarchy(employees, depth_level)
    
    # Prepend Organization Root
    org_root = OrgChartNode(
        entity_type="organization",
        id=str(current_org.uuid),
        name=current_org.name,
        children=hierarchy
    )
    
    return OrgChartResponse(
        success=True,
        message="Organization chart retrieved successfully",
        data=[org_root]
    )
