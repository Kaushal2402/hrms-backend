from typing import Optional, List
from sqlalchemy.orm import Session
from sqlalchemy import or_, and_
from datetime import date
from app.models.attendance import LeavePolicy
from app.models.employee import Employee

def get_applicable_policy(db: Session, employee_id: int, target_date: Optional[date] = None) -> Optional[LeavePolicy]:
    """
    Find the most relevant leave policy for an employee on a specific date.
    Priority Hierarchy:
    1. Department Specific Policy
    2. Location Specific Policy
    3. Employment Type Specific Policy
    4. Global 'all' Policy
    5. Organization Default Policy
    """
    if target_date is None:
        target_date = date.today()
        
    employee = db.query(Employee).filter(Employee.id == employee_id, Employee.is_deleted == False).first()
    if not employee:
        return None
        
    # Get all active policies for the organization that cover the target date
    # Ordered by priority-influencing fields (this is a simplified approach, 
    # we'll do manual filtering to ensure exact priority)
    policies = db.query(LeavePolicy).filter(
        LeavePolicy.organization_id == employee.organization_id,
        LeavePolicy.is_active == True,
        LeavePolicy.is_deleted == False,
        LeavePolicy.effective_from <= target_date,
        or_(
            LeavePolicy.effective_to >= target_date,
            LeavePolicy.effective_to == None
        )
    ).all()
    
    if not policies:
        return None
        
    # Priority 1: Department match
    if employee.department_id:
        dept_policies = [p for p in policies if p.applicable_to == "department" and p.department_ids and employee.department_id in p.department_ids]
        if dept_policies:
            return dept_policies[0]
            
    # Priority 2: Location match
    if employee.location_id:
        loc_policies = [p for p in policies if p.applicable_to == "location" and p.location_ids and employee.location_id in p.location_ids]
        if loc_policies:
            return loc_policies[0]
            
    # Priority 3: Employment Type match
    if employee.employment_type:
        et_policies = [p for p in policies if p.employment_types and employee.employment_type in p.employment_types]
        if et_policies:
            return et_policies[0]
            
    # Priority 4: Organization-wide policies
    global_policies = [p for p in policies if p.applicable_to == "all"]
    if global_policies:
        return global_policies[0]
        
    # Priority 5: Fallback to Default policy
    default_policies = [p for p in policies if p.is_default]
    if default_policies:
        return default_policies[0]
        
    return None
