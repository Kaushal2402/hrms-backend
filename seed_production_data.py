from sqlalchemy.orm import Session
from app.db.session import SessionLocal
from app.models.organization import Industry
from app.models.industry_templates import (
    IndustryDepartmentTemplate, IndustryJobTitleTemplate, IndustryRoleTemplate,
    IndustryShiftTemplate, IndustryAttendancePolicyTemplate, MasterCountryHoliday,
    IndustryLeaveTypeTemplate, IndustryLeavePolicyTemplate
)
from datetime import time, date

def seed_production():
    db = SessionLocal()
    print("Starting production seeding...")
    
    # 1. Seed Industries
    industries = [
        "Information Technology", "Healthcare & Pharma", "Education & E-Learning",
        "Manufacturing", "Retail & E-commerce", "Hospitality & Tourism",
        "Banking & Finance", "Construction & Real Estate", "Professional Services"
    ]
    
    for ind_name in industries:
        if not db.query(Industry).filter_by(name=ind_name).first():
            db.add(Industry(name=ind_name, description=f"Default {ind_name} industry"))
    
    db.commit()
    print(f"✓ Seeded {len(industries)} Industries")

    # 2. Seed IT Templates (as the primary default)
    it_industry = db.query(Industry).filter(Industry.name == "Information Technology").first()
    if not it_industry:
        print("Error: IT Industry not found after seeding.")
        return

    ind_id = it_industry.id

    # Departments
    depts = [
        {"department_code": "ENG", "department_name": "Engineering", "description": "Software development and engineering"},
        {"department_code": "QA", "department_name": "Quality Assurance", "description": "Testing and quality control"},
        {"department_code": "PROD", "department_name": "Product Management", "description": "Product roadmap and strategy"},
        {"department_code": "OPS", "department_name": "Operations", "description": "System admin and devops"},
        {"department_code": "HR", "department_name": "Human Resources", "description": "Talent acquisition and management"},
    ]
    for d in depts:
        if not db.query(IndustryDepartmentTemplate).filter_by(department_code=d["department_code"], industry_id=ind_id).first():
            db.add(IndustryDepartmentTemplate(industry_id=ind_id, **d))

    # Job Titles
    titles = [
        {"title_code": "SWE", "title_name": "Software Engineer", "job_level": "Mid", "job_family": "Engineering"},
        {"title_code": "SSWE", "title_name": "Senior Software Engineer", "job_level": "Senior", "job_family": "Engineering"},
        {"title_code": "TL", "title_name": "Team Lead", "job_level": "Lead", "job_family": "Engineering"},
        {"title_code": "PM", "title_name": "Product Manager", "job_level": "Mid", "job_family": "Product"},
        {"title_code": "QAE", "title_name": "QA Engineer", "job_level": "Mid", "job_family": "QA"},
    ]
    for t in titles:
        if not db.query(IndustryJobTitleTemplate).filter_by(title_code=t["title_code"], industry_id=ind_id).first():
            db.add(IndustryJobTitleTemplate(industry_id=ind_id, **t))

    # Roles
    roles = [
        {
            "role_code": "IT_MANAGER", 
            "role_name": "IT Manager", 
            "permission_codes": ["1", "2", "3", "4", "5", "6", "7", "8"]
        },
        {
            "role_code": "TEAM_LEAD", 
            "role_name": "Team Lead", 
            "permission_codes": ["1", "5", "9", "13", "33", "55"]
        }
    ]
    for r in roles:
        if not db.query(IndustryRoleTemplate).filter_by(role_code=r["role_code"], industry_id=ind_id).first():
            db.add(IndustryRoleTemplate(industry_id=ind_id, **r))

    # Shifts
    s_data = {
        "shift_code": "GEN",
        "shift_name": "General Shift",
        "shift_type": "fixed",
        "start_time": time(9, 0),
        "end_time": time(18, 0),
        "work_hours": 9.0,
        "has_break": True,
        "break_hours": 1.0,
        "week_off_days": [0, 6]
    }
    if not db.query(IndustryShiftTemplate).filter_by(shift_code=s_data["shift_code"], industry_id=ind_id).first():
        db.add(IndustryShiftTemplate(industry_id=ind_id, **s_data))

    # Attendance Policy
    policies = [
        {
            "policy_name": "Standard IT Policy", "working_days_per_week": 5,
            "working_hours_per_day": 8.0, "late_arrival_grace": 15,
            "overtime_enabled": True, "regularization_allowed": True
        }
    ]
    for p in policies:
        if not db.query(IndustryAttendancePolicyTemplate).filter_by(policy_name=p["policy_name"], industry_id=ind_id).first():
            db.add(IndustryAttendancePolicyTemplate(industry_id=ind_id, **p))

    # Leave Types
    leave_types = [
        {"leave_code": "CL", "leave_name": "Casual Leave", "accrual_type": "monthly", "accrual_rate": 1.0, "annual_quota": 12, "color_code": "#FF5733"},
        {"leave_code": "SL", "leave_name": "Sick Leave", "accrual_type": "monthly", "accrual_rate": 1.0, "annual_quota": 12, "color_code": "#33FF57"},
        {"leave_code": "PL", "leave_name": "Privilege Leave", "accrual_type": "yearly", "accrual_rate": 15.0, "annual_quota": 15, "color_code": "#3357FF"},
    ]
    for lt in leave_types:
        if not db.query(IndustryLeaveTypeTemplate).filter_by(leave_code=lt["leave_code"], industry_id=ind_id).first():
            db.add(IndustryLeaveTypeTemplate(industry_id=ind_id, **lt))

    # Leave Policies
    leave_policies = [
        {
            "policy_name": "Standard IT Leave Policy",
            "description": "Default leave policy for IT employees",
            "leave_type_codes": ["CL", "SL", "PL"]
        }
    ]
    for lp in leave_policies:
        if not db.query(IndustryLeavePolicyTemplate).filter_by(policy_name=lp["policy_name"], industry_id=ind_id).first():
            db.add(IndustryLeavePolicyTemplate(industry_id=ind_id, **lp))

    # Master Holidays
    holidays = [
        {"holiday_name": "New Year's Day", "holiday_date": date(2026, 1, 1), "holiday_type": "public", "country": "India"},
        {"holiday_name": "Republic Day", "holiday_date": date(2026, 1, 26), "holiday_type": "public", "country": "India"},
        {"holiday_name": "Independence Day", "holiday_date": date(2026, 8, 15), "holiday_type": "public", "country": "India"},
        {"holiday_name": "Gandhi Jayanti", "holiday_date": date(2026, 10, 2), "holiday_type": "public", "country": "India"},
        {"holiday_name": "Christmas Day", "holiday_date": date(2026, 12, 25), "holiday_type": "public", "country": "India"},
    ]
    for h in holidays:
        if not db.query(MasterCountryHoliday).filter_by(holiday_name=h["holiday_name"], country=h["country"]).first():
            db.add(MasterCountryHoliday(**h))

    db.commit()
    db.close()
    print("✓ Production Templates seeded successfully.")

if __name__ == "__main__":
    seed_production()
