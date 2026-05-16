import os
import sys
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# Add backend_api to sys.path
sys.path.append('/Users/softpital/HRM/backend_api')

from app.db.session import SessionLocal
from app.models.payroll import Payslip, PayrollPeriod
from app.models.employee import Employee, Department
from app.schemas.payroll_payslips import PayslipSchema

def test_query():
    db = SessionLocal()
    try:
        result = db.query(Payslip, Employee, Department, PayrollPeriod)\
            .join(Employee, Payslip.employee_id == Employee.id)\
            .outerjoin(Department, Employee.department_id == Department.id)\
            .join(PayrollPeriod, Payslip.payroll_period_id == PayrollPeriod.id)\
            .first()
        
        if result:
            payslip, emp, dept, period = result
            print(f"Payslip: {payslip.payslip_number}")
            print(f"Employee: {emp.first_name}")
            print(f"Dept: {dept.department_name if dept else 'None'}")
            print(f"Period: {period.period_name}")
            
            p_schema = PayslipSchema.model_validate(payslip)
            p_schema.employee_name = f"{emp.first_name} {emp.last_name}"
            p_schema.employee_code = emp.employee_code
            p_schema.department_name = dept.department_name if dept else None
            p_schema.period_name = period.period_name
            print("Validation successful")
        else:
            print("No payslips found")
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        db.close()

if __name__ == "__main__":
    test_query()
