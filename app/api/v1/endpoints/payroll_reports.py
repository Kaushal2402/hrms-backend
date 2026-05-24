import uuid
from decimal import Decimal
from typing import Optional, Union

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.api import deps
from app.models.organization import Organization
from app.models.employee import Employee, Department, Location, CostCenter
from app.models.payroll import Payslip, PayrollPeriod, PayslipComponent
from app.schemas.payroll_reports import (
    PayrollSummaryReportResponse, 
    ComponentWiseReportResponse, 
    DepartmentWiseReportResponse,
    PayrollVarianceReportResponse,
    CostCenterAllocationResponse,
    TaxDeductionReportResponse,
    LoanRecoveryReportResponse,
    SalaryRegisterReportResponse,
    YTDEarningsReportResponse,
    PayrollCostProjectionResponse
)
from app.core.permissions import PayrollReportPermissions

router = APIRouter()


def _require_permission(db: Session, current_user: Union[Organization, Employee], code: str, action: str):
    if isinstance(current_user, Organization):
        return
    if not deps.has_permission(db, current_user, code):
        raise HTTPException(status_code=403, detail=f"Permission denied: {action}")


@router.get("/payroll-summary", response_model=PayrollSummaryReportResponse)
def get_payroll_summary(
    period_id: Optional[uuid.UUID] = Query(None, description="UUID of a specific payroll period"),
    financial_year: Optional[str] = Query(None, description="Financial year, e.g. 'FY 2024-25'"),
    department_id: Optional[uuid.UUID] = Query(None, description="UUID of department to filter by"),
    location_id: Optional[uuid.UUID] = Query(None, description="UUID of location to filter by"),
    db: Session = Depends(deps.get_db),
    current_org: Organization = Depends(deps.get_current_org),
    current_user: Union[Organization, Employee] = Depends(deps.get_current_user),
):
    _require_permission(db, current_user, PayrollReportPermissions.READ, "view payroll summary report")

    if not period_id and not financial_year:
        raise HTTPException(status_code=400, detail="Provide at least one of: period_id or financial_year")

    period_name = None
    period_ids: list[int] = []

    if period_id:
        period = db.query(PayrollPeriod).filter(
            PayrollPeriod.uuid == period_id,
            PayrollPeriod.organization_id == current_org.id,
        ).first()
        if not period:
            raise HTTPException(status_code=404, detail="Payroll period not found")
        period_ids = [period.id]
        period_name = period.period_name
        if not financial_year:
            financial_year = period.financial_year
    else:
        periods = db.query(PayrollPeriod).filter(
            PayrollPeriod.organization_id == current_org.id,
            PayrollPeriod.financial_year == financial_year,
        ).all()
        period_ids = [p.id for p in periods]
        if not period_ids:
            raise HTTPException(status_code=404, detail="No payroll periods found for the given financial year")

    query = db.query(Payslip).filter(
        Payslip.organization_id == current_org.id,
        Payslip.payroll_period_id.in_(period_ids),
    )

    needs_employee_join = bool(department_id or location_id)
    if needs_employee_join:
        query = query.join(Employee, Payslip.employee_id == Employee.id)

    if department_id:
        dept = db.query(Department).filter(Department.uuid == department_id).first()
        if not dept:
            raise HTTPException(status_code=404, detail="Department not found")
        query = query.filter(Employee.department_id == dept.id)

    if location_id:
        loc = db.query(Location).filter(Location.uuid == location_id).first()
        if not loc:
            raise HTTPException(status_code=404, detail="Location not found")
        query = query.filter(Employee.location_id == loc.id)

    agg = query.with_entities(
        func.count(Payslip.id).label("total_employees"),
        func.coalesce(func.sum(Payslip.gross_salary), 0).label("total_gross"),
        func.coalesce(func.sum(Payslip.net_salary), 0).label("total_net"),
        func.coalesce(func.sum(Payslip.total_deductions), 0).label("total_deductions"),
        func.coalesce(func.sum(Payslip.total_employer_contributions), 0).label("total_employer_contributions"),
        func.coalesce(func.sum(Payslip.tax_deducted), 0).label("total_tax_deducted"),
        func.coalesce(func.sum(Payslip.lop_amount), 0).label("total_lop_amount"),
        func.coalesce(func.sum(Payslip.arrears_amount), 0).label("total_arrears"),
        func.coalesce(func.sum(Payslip.one_time_payments), 0).label("total_one_time_payments"),
        func.coalesce(func.sum(Payslip.overtime_amount), 0).label("total_overtime_amount"),
        func.coalesce(func.sum(Payslip.total_reimbursements), 0).label("total_reimbursements"),
    ).one()

    total_employees = agg.total_employees or 0
    total_gross = Decimal(str(agg.total_gross or 0))
    total_net = Decimal(str(agg.total_net or 0))
    avg_gross = (total_gross / total_employees).quantize(Decimal("0.01")) if total_employees > 0 else Decimal("0.00")
    avg_net = (total_net / total_employees).quantize(Decimal("0.01")) if total_employees > 0 else Decimal("0.00")

    return {
        "success": True,
        "message": "Payroll summary report generated successfully",
        "data": {
            "total_employees": total_employees,
            "total_gross": total_gross,
            "total_net": total_net,
            "total_deductions": Decimal(str(agg.total_deductions or 0)),
            "total_employer_contributions": Decimal(str(agg.total_employer_contributions or 0)),
            "total_tax_deducted": Decimal(str(agg.total_tax_deducted or 0)),
            "total_lop_amount": Decimal(str(agg.total_lop_amount or 0)),
            "total_arrears": Decimal(str(agg.total_arrears or 0)),
            "total_one_time_payments": Decimal(str(agg.total_one_time_payments or 0)),
            "total_overtime_amount": Decimal(str(agg.total_overtime_amount or 0)),
            "total_reimbursements": Decimal(str(agg.total_reimbursements or 0)),
            "average_gross": avg_gross,
            "average_net": avg_net,
            "period_name": period_name,
            "financial_year": financial_year,
        },
    }


@router.get("/component-wise", response_model=ComponentWiseReportResponse)
def get_component_wise_report(
    period_id: uuid.UUID = Query(..., description="UUID of the payroll period"),
    component_ids: Optional[list[int]] = Query(None, description="Optional list of component IDs to filter"),
    db: Session = Depends(deps.get_db),
    current_org: Organization = Depends(deps.get_current_org),
    current_user: Union[Organization, Employee] = Depends(deps.get_current_user),
):
    _require_permission(db, current_user, PayrollReportPermissions.READ, "view component-wise report")

    period = db.query(PayrollPeriod).filter(
        PayrollPeriod.uuid == period_id,
        PayrollPeriod.organization_id == current_org.id,
    ).first()

    if not period:
        raise HTTPException(status_code=404, detail="Payroll period not found")

    query = db.query(
        PayslipComponent.component_id,
        PayslipComponent.component_name,
        PayslipComponent.component_type,
        func.count(func.distinct(Payslip.employee_id)).label("employee_count"),
        func.coalesce(func.sum(PayslipComponent.actual_amount), 0).label("total_amount")
    ).join(
        Payslip, PayslipComponent.payslip_id == Payslip.id
    ).filter(
        Payslip.organization_id == current_org.id,
        Payslip.payroll_period_id == period.id,
    )

    if component_ids:
        query = query.filter(PayslipComponent.component_id.in_(component_ids))

    query = query.group_by(
        PayslipComponent.component_id,
        PayslipComponent.component_name,
        PayslipComponent.component_type
    )

    results = query.all()

    # We also need total unique employees processed in this period
    total_employees = db.query(func.count(func.distinct(Payslip.employee_id))).filter(
        Payslip.organization_id == current_org.id,
        Payslip.payroll_period_id == period.id
    ).scalar() or 0

    data = []
    for r in results:
        total_amt = Decimal(str(r.total_amount))
        emp_count = r.employee_count or 0
        avg_amt = (total_amt / emp_count).quantize(Decimal("0.01")) if emp_count > 0 else Decimal("0.00")
        
        data.append({
            "component_id": r.component_id,
            "component_name": r.component_name,
            "component_type": r.component_type,
            "total_amount": total_amt,
            "average_amount": avg_amt,
            "employee_count": emp_count
        })

    return {
        "success": True,
        "message": "Component-wise report generated successfully",
        "period_name": period.period_name,
        "total_employees": total_employees,
        "data": data
    }


@router.get("/department-wise", response_model=DepartmentWiseReportResponse)
def get_department_wise_report(
    period_id: Optional[uuid.UUID] = Query(None, description="UUID of a specific payroll period"),
    financial_year: Optional[str] = Query(None, description="Financial year, e.g. 'FY 2024-25'"),
    db: Session = Depends(deps.get_db),
    current_org: Organization = Depends(deps.get_current_org),
    current_user: Union[Organization, Employee] = Depends(deps.get_current_user),
):
    _require_permission(db, current_user, PayrollReportPermissions.READ, "view department-wise report")

    if not period_id and not financial_year:
        raise HTTPException(status_code=400, detail="Provide at least one of: period_id or financial_year")

    period_name = None
    period_ids: list[int] = []

    if period_id:
        period = db.query(PayrollPeriod).filter(
            PayrollPeriod.uuid == period_id,
            PayrollPeriod.organization_id == current_org.id,
        ).first()
        if not period:
            raise HTTPException(status_code=404, detail="Payroll period not found")
        period_ids = [period.id]
        period_name = period.period_name
        if not financial_year:
            financial_year = period.financial_year
    else:
        periods = db.query(PayrollPeriod).filter(
            PayrollPeriod.organization_id == current_org.id,
            PayrollPeriod.financial_year == financial_year,
        ).all()
        period_ids = [p.id for p in periods]
        if not period_ids:
            raise HTTPException(status_code=404, detail="No payroll periods found for the given financial year")

    query = db.query(
        Employee.department_id,
        func.max(Department.department_name).label("department_name"),
        func.count(func.distinct(Payslip.employee_id)).label("employee_count"),
        func.coalesce(func.sum(Payslip.gross_salary), 0).label("total_gross"),
        func.coalesce(func.sum(Payslip.net_salary), 0).label("total_net"),
        func.coalesce(func.sum(Payslip.total_employer_contributions), 0).label("total_employer_contributions"),
    ).join(
        Employee, Payslip.employee_id == Employee.id
    ).outerjoin(
        Department, Employee.department_id == Department.id
    ).filter(
        Payslip.organization_id == current_org.id,
        Payslip.payroll_period_id.in_(period_ids),
    ).group_by(
        Employee.department_id
    )

    results = query.all()

    data = []
    for r in results:
        t_gross = Decimal(str(r.total_gross))
        t_net = Decimal(str(r.total_net))
        t_emp_contrib = Decimal(str(r.total_employer_contributions))
        
        data.append({
            "department_id": r.department_id,
            "department_name": r.department_name or "Unassigned",
            "employee_count": r.employee_count or 0,
            "total_gross": t_gross,
            "total_net": t_net,
            "total_employer_contributions": t_emp_contrib,
            "total_cost": t_gross + t_emp_contrib
        })

    return {
        "success": True,
        "message": "Department-wise report generated successfully",
        "period_name": period_name,
        "financial_year": financial_year,
        "data": data
    }


@router.get("/variance", response_model=PayrollVarianceReportResponse)
def get_payroll_variance_report(
    current_period_id: uuid.UUID = Query(..., description="UUID of the current payroll period"),
    compare_period_id: uuid.UUID = Query(..., description="UUID of the previous/comparison payroll period"),
    db: Session = Depends(deps.get_db),
    current_org: Organization = Depends(deps.get_current_org),
    current_user: Union[Organization, Employee] = Depends(deps.get_current_user),
):
    _require_permission(db, current_user, PayrollReportPermissions.READ, "view payroll variance report")

    current_period = db.query(PayrollPeriod).filter(
        PayrollPeriod.uuid == current_period_id,
        PayrollPeriod.organization_id == current_org.id,
    ).first()
    
    if not current_period:
        raise HTTPException(status_code=404, detail="Current payroll period not found")

    compare_period = db.query(PayrollPeriod).filter(
        PayrollPeriod.uuid == compare_period_id,
        PayrollPeriod.organization_id == current_org.id,
    ).first()
    
    if not compare_period:
        raise HTTPException(status_code=404, detail="Comparison payroll period not found")

    def get_period_stats(p_id: int):
        return db.query(
            func.count(func.distinct(Payslip.employee_id)).label("employee_count"),
            func.coalesce(func.sum(Payslip.gross_salary), 0).label("total_gross"),
            func.coalesce(func.sum(Payslip.net_salary), 0).label("total_net"),
            func.coalesce(func.sum(Payslip.total_deductions), 0).label("total_deductions"),
            func.coalesce(func.sum(Payslip.tax_deducted), 0).label("total_tax_deducted"),
            func.coalesce(func.sum(Payslip.total_employer_contributions), 0).label("total_employer_contributions"),
        ).filter(
            Payslip.organization_id == current_org.id,
            Payslip.payroll_period_id == p_id,
        ).first()

    current_stats = get_period_stats(current_period.id)
    compare_stats = get_period_stats(compare_period.id)

    def _calc_variance(curr, prev):
        curr_val = Decimal(str(curr))
        prev_val = Decimal(str(prev))
        abs_var = curr_val - prev_val
        pct_var = 0.0
        if prev_val > 0:
            pct_var = float((abs_var / prev_val) * 100)
        elif curr_val > 0:
            pct_var = 100.0
        return curr_val, prev_val, abs_var, round(pct_var, 2)

    variance_data = []
    metrics = [
        ("Total Gross", current_stats.total_gross, compare_stats.total_gross),
        ("Total Net", current_stats.total_net, compare_stats.total_net),
        ("Total Deductions", current_stats.total_deductions, compare_stats.total_deductions),
        ("Tax Deducted (TDS)", current_stats.total_tax_deducted, compare_stats.total_tax_deducted),
        ("Employer Contributions", current_stats.total_employer_contributions, compare_stats.total_employer_contributions),
    ]

    for label, curr, prev in metrics:
        curr_val, prev_val, abs_var, pct_var = _calc_variance(curr, prev)
        variance_data.append({
            "label": label,
            "current_value": curr_val,
            "previous_value": prev_val,
            "absolute_variance": abs_var,
            "percentage_variance": pct_var
        })

    return {
        "success": True,
        "message": "Variance report generated successfully",
        "current_period_name": current_period.period_name,
        "compare_period_name": compare_period.period_name,
        "current_employee_count": current_stats.employee_count or 0,
        "previous_employee_count": compare_stats.employee_count or 0,
        "variance": variance_data
    }


@router.get("/cost-center-allocation", response_model=CostCenterAllocationResponse)
def get_cost_center_allocation_report(
    period_id: uuid.UUID = Query(..., description="UUID of a specific payroll period"),
    db: Session = Depends(deps.get_db),
    current_org: Organization = Depends(deps.get_current_org),
    current_user: Union[Organization, Employee] = Depends(deps.get_current_user),
):
    _require_permission(db, current_user, PayrollReportPermissions.READ, "view cost center allocation report")

    period = db.query(PayrollPeriod).filter(
        PayrollPeriod.uuid == period_id,
        PayrollPeriod.organization_id == current_org.id,
    ).first()
    if not period:
        raise HTTPException(status_code=404, detail="Payroll period not found")

    # Get total org cost for the period
    org_totals = db.query(
        func.coalesce(func.sum(Payslip.gross_salary), 0).label("total_gross"),
        func.coalesce(func.sum(Payslip.total_employer_contributions), 0).label("total_employer_contributions")
    ).filter(
        Payslip.organization_id == current_org.id,
        Payslip.payroll_period_id == period.id
    ).first()
    
    total_org_gross = Decimal(str(org_totals.total_gross))
    total_org_employer_contributions = Decimal(str(org_totals.total_employer_contributions))
    total_org_cost = total_org_gross + total_org_employer_contributions

    query = db.query(
        Employee.cost_center_id,
        func.max(CostCenter.cost_center_name).label("cost_center_name"),
        func.max(CostCenter.cost_center_code).label("cost_center_code"),
        func.count(func.distinct(Payslip.employee_id)).label("employee_count"),
        func.coalesce(func.sum(Payslip.gross_salary), 0).label("total_gross"),
        func.coalesce(func.sum(Payslip.net_salary), 0).label("total_net"),
        func.coalesce(func.sum(Payslip.total_employer_contributions), 0).label("total_employer_contributions"),
    ).join(
        Employee, Payslip.employee_id == Employee.id
    ).outerjoin(
        CostCenter, Employee.cost_center_id == CostCenter.id
    ).filter(
        Payslip.organization_id == current_org.id,
        Payslip.payroll_period_id == period.id,
    ).group_by(
        Employee.cost_center_id
    )

    results = query.all()

    data = []
    for r in results:
        t_gross = Decimal(str(r.total_gross))
        t_net = Decimal(str(r.total_net))
        t_emp_contrib = Decimal(str(r.total_employer_contributions))
        t_cost = t_gross + t_emp_contrib
        
        allocation_percentage = 0.0
        if total_org_cost > 0:
            allocation_percentage = float((t_cost / total_org_cost) * 100)
            
        data.append({
            "cost_center_id": r.cost_center_id,
            "cost_center_name": r.cost_center_name or "Unassigned",
            "cost_center_code": r.cost_center_code,
            "employee_count": r.employee_count or 0,
            "total_gross": t_gross,
            "total_net": t_net,
            "total_employer_contributions": t_emp_contrib,
            "total_cost": t_cost,
            "allocation_percentage": round(allocation_percentage, 2)
        })

    # Sort by total_cost descending to show largest allocations first
    data.sort(key=lambda x: x["total_cost"], reverse=True)

    return {
        "success": True,
        "message": "Cost center allocation report generated successfully",
        "period_name": period.period_name,
        "total_org_cost": total_org_cost,
        "data": data
    }


@router.get("/tax-deduction", response_model=TaxDeductionReportResponse)
def get_tax_deduction_report(
    financial_year: str = Query(..., description="Financial year, e.g. 'FY 2024-25'"),
    quarter: Optional[int] = Query(None, description="Quarter 1-4 (optional)"),
    db: Session = Depends(deps.get_db),
    current_org: Organization = Depends(deps.get_current_org),
    current_user: Union[Organization, Employee] = Depends(deps.get_current_user),
):
    _require_permission(db, current_user, PayrollReportPermissions.READ, "view tax deduction report")

    from sqlalchemy import extract
    
    # Base query for periods in the financial year
    period_query = db.query(PayrollPeriod).filter(
        PayrollPeriod.organization_id == current_org.id,
        PayrollPeriod.financial_year == financial_year
    )
    
    if quarter is not None:
        if quarter == 1:
            period_query = period_query.filter(extract('month', PayrollPeriod.period_start_date).in_([4, 5, 6]))
        elif quarter == 2:
            period_query = period_query.filter(extract('month', PayrollPeriod.period_start_date).in_([7, 8, 9]))
        elif quarter == 3:
            period_query = period_query.filter(extract('month', PayrollPeriod.period_start_date).in_([10, 11, 12]))
        elif quarter == 4:
            period_query = period_query.filter(extract('month', PayrollPeriod.period_start_date).in_([1, 2, 3]))

    periods = period_query.all()
    if not periods:
        return {
            "success": True,
            "message": "No periods found for the specified criteria",
            "financial_year": financial_year,
            "quarter": quarter,
            "total_tds": 0,
            "total_employees": 0,
            "data": []
        }
    
    period_ids = [p.id for p in periods]

    query = db.query(
        Employee.uuid.label("employee_uuid"),
        func.max(Employee.employee_code).label("employee_code"),
        func.max(Employee.first_name + ' ' + Employee.last_name).label("employee_name"),
        func.max(Department.department_name).label("department_name"),
        func.max(Employee.pan_number).label("pan_number"),
        func.coalesce(func.sum(Payslip.tax_deducted), 0).label("total_tds_deducted"),
        func.coalesce(func.sum(Payslip.gross_salary), 0).label("total_gross_income"),
        func.coalesce(func.sum(Payslip.net_salary), 0).label("total_net_income"),
        func.count(Payslip.id).label("periods_included")
    ).join(
        Employee, Payslip.employee_id == Employee.id
    ).outerjoin(
        Department, Employee.department_id == Department.id
    ).filter(
        Payslip.organization_id == current_org.id,
        Payslip.payroll_period_id.in_(period_ids),
        Payslip.tax_deducted > 0
    ).group_by(
        Employee.uuid
    )

    results = query.all()
    
    data = []
    total_tds_all = Decimal('0')
    
    for r in results:
        tds = Decimal(str(r.total_tds_deducted))
        total_tds_all += tds
        data.append({
            "employee_uuid": r.employee_uuid,
            "employee_code": r.employee_code or "Unknown",
            "employee_name": r.employee_name or "Unknown",
            "department": r.department_name or "Unassigned",
            "pan_number": r.pan_number,
            "total_tds_deducted": tds,
            "total_gross_income": Decimal(str(r.total_gross_income)),
            "total_net_income": Decimal(str(r.total_net_income)),
            "periods_included": r.periods_included
        })

    return {
        "success": True,
        "message": "Tax deduction report generated successfully",
        "financial_year": financial_year,
        "quarter": quarter,
        "total_tds": total_tds_all,
        "total_employees": len(data),
        "data": data
    }


@router.get("/loan-recovery", response_model=LoanRecoveryReportResponse)
def get_loan_recovery_report(
    period_id: uuid.UUID = Query(..., description="UUID of a specific payroll period"),
    status: Optional[str] = Query(None, description="Filter by loan status (e.g. active, completed)"),
    db: Session = Depends(deps.get_db),
    current_org: Organization = Depends(deps.get_current_org),
    current_user: Union[Organization, Employee] = Depends(deps.get_current_user),
):
    from app.models.payroll import EmployeeLoan, LoanRepayment
    
    _require_permission(db, current_user, PayrollReportPermissions.READ, "view loan recovery report")

    period = db.query(PayrollPeriod).filter(
        PayrollPeriod.uuid == period_id,
        PayrollPeriod.organization_id == current_org.id,
    ).first()
    if not period:
        raise HTTPException(status_code=404, detail="Payroll period not found")

    query = db.query(
        Employee.uuid.label("employee_uuid"),
        Employee.employee_code,
        (Employee.first_name + ' ' + Employee.last_name).label("employee_name"),
        EmployeeLoan.loan_number,
        EmployeeLoan.loan_type,
        EmployeeLoan.status.label("loan_status"),
        EmployeeLoan.outstanding_amount,
        func.coalesce(func.sum(LoanRepayment.principal_amount), 0).label("principal_recovered"),
        func.coalesce(func.sum(LoanRepayment.interest_amount), 0).label("interest_recovered"),
        func.coalesce(func.sum(LoanRepayment.total_amount), 0).label("total_recovered")
    ).join(
        EmployeeLoan, LoanRepayment.loan_id == EmployeeLoan.id
    ).join(
        Employee, EmployeeLoan.employee_id == Employee.id
    ).filter(
        EmployeeLoan.organization_id == current_org.id,
        LoanRepayment.payroll_period_id == period.id,
        LoanRepayment.is_paid == True
    )
    
    if status:
        query = query.filter(EmployeeLoan.status == status)
        
    query = query.group_by(
        Employee.uuid,
        Employee.employee_code,
        Employee.first_name,
        Employee.last_name,
        EmployeeLoan.loan_number,
        EmployeeLoan.loan_type,
        EmployeeLoan.status,
        EmployeeLoan.outstanding_amount
    )

    results = query.all()
    
    data = []
    total_recovered_all = Decimal('0')
    
    for r in results:
        tot_rec = Decimal(str(r.total_recovered))
        total_recovered_all += tot_rec
        
        data.append({
            "employee_uuid": r.employee_uuid,
            "employee_code": r.employee_code or "Unknown",
            "employee_name": r.employee_name or "Unknown",
            "loan_number": r.loan_number,
            "loan_type": r.loan_type,
            "principal_recovered": Decimal(str(r.principal_recovered)),
            "interest_recovered": Decimal(str(r.interest_recovered)),
            "total_recovered": tot_rec,
            "outstanding_balance": Decimal(str(r.outstanding_amount)),
            "status": r.loan_status.value if hasattr(r.loan_status, 'value') else str(r.loan_status)
        })

    return {
        "success": True,
        "message": "Loan recovery report generated successfully",
        "period_name": period.period_name,
        "status_filter": status,
        "total_recovered": total_recovered_all,
        "data": data
    }


@router.get("/salary-register", response_model=SalaryRegisterReportResponse)
def get_salary_register_report(
    period_id: uuid.UUID = Query(..., description="UUID of a specific payroll period"),
    department_id: Optional[uuid.UUID] = Query(None, description="Optional department UUID filter"),
    format: str = Query("json", description="Format of report (json, pdf, excel)"),
    db: Session = Depends(deps.get_db),
    current_org: Organization = Depends(deps.get_current_org),
    current_user: Union[Organization, Employee] = Depends(deps.get_current_user),
):
    from app.models.payroll import EmployeeBankAccount
    
    _require_permission(db, current_user, PayrollReportPermissions.READ, "view salary register")

    period = db.query(PayrollPeriod).filter(
        PayrollPeriod.uuid == period_id,
        PayrollPeriod.organization_id == current_org.id,
    ).first()
    if not period:
        raise HTTPException(status_code=404, detail="Payroll period not found")

    query = db.query(
        Payslip, Employee, Department, Location, EmployeeBankAccount
    ).join(
        Employee, Payslip.employee_id == Employee.id
    ).outerjoin(
        Department, Employee.department_id == Department.id
    ).outerjoin(
        Location, Employee.location_id == Location.id
    ).outerjoin(
        EmployeeBankAccount, Employee.id == EmployeeBankAccount.employee_id
    ).filter(
        Payslip.organization_id == current_org.id,
        Payslip.payroll_period_id == period.id
    )

    if department_id:
        dept = db.query(Department).filter(Department.uuid == department_id).first()
        if dept:
            query = query.filter(Employee.department_id == dept.id)

    results = query.all()

    # Bulk fetch components for all payslips to avoid N+1
    payslip_ids = [r.Payslip.id for r in results]
    components = []
    if payslip_ids:
        components = db.query(PayslipComponent).filter(
            PayslipComponent.payslip_id.in_(payslip_ids)
        ).all()
        
    comp_map = {}
    for c in components:
        if c.payslip_id not in comp_map:
            comp_map[c.payslip_id] = []
        comp_map[c.payslip_id].append(c)

    data = []
    for r in results:
        ps = r.Payslip
        emp = r.Employee
        dept = r.Department
        loc = r.Location
        bank = r.EmployeeBankAccount
        
        comps = []
        if ps.id in comp_map:
            for c in comp_map[ps.id]:
                comps.append({
                    "component_name": c.component_name,
                    "component_type": str(c.component_type.value) if hasattr(c.component_type, 'value') else str(c.component_type),
                    "amount": Decimal(str(c.actual_amount))
                })

        data.append({
            "employee_uuid": emp.uuid,
            "employee_code": emp.employee_code,
            "employee_name": f"{emp.first_name} {emp.last_name}",
            "department": dept.department_name if dept else None,
            "location": loc.location_name if loc else None,
            "designation": emp.job_title_name if hasattr(emp, 'job_title_name') else None,
            "bank_account_number": bank.account_number if bank and hasattr(bank, 'account_number') else None,
            "ifsc_code": bank.ifsc_code if bank and hasattr(bank, 'ifsc_code') else None,
            "days_present": Decimal(str(ps.days_present)),
            "lop_days": Decimal(str(ps.lop_days)),
            "gross_salary": Decimal(str(ps.gross_salary)),
            "total_deductions": Decimal(str(ps.total_deductions)),
            "net_salary": Decimal(str(ps.net_salary)),
            "tax_deducted": Decimal(str(ps.tax_deducted)),
            "components": comps
        })

    return {
        "success": True,
        "message": "Salary register generated successfully",
        "period_name": period.period_name,
        "total_employees": len(data),
        "format": format,
        "data": data
    }


@router.get("/ytd-earnings", response_model=YTDEarningsReportResponse)
def get_ytd_earnings_report(
    financial_year: str = Query(..., description="Financial year, e.g. 'FY 2024-25'"),
    employee_id: Optional[uuid.UUID] = Query(None, description="Specific employee UUID"),
    department_id: Optional[uuid.UUID] = Query(None, description="Specific department UUID"),
    db: Session = Depends(deps.get_db),
    current_org: Organization = Depends(deps.get_current_org),
    current_user: Union[Organization, Employee] = Depends(deps.get_current_user),
):
    _require_permission(db, current_user, PayrollReportPermissions.READ, "view YTD earnings report")

    # Get periods in financial year
    periods = db.query(PayrollPeriod).filter(
        PayrollPeriod.organization_id == current_org.id,
        PayrollPeriod.financial_year == financial_year
    ).all()
    
    if not periods:
        return {
            "success": True,
            "message": "No periods found for the specified financial year",
            "financial_year": financial_year,
            "total_employees": 0,
            "data": []
        }
        
    period_ids = [p.id for p in periods]
    period_map = {p.id: p for p in periods}

    query = db.query(
        Employee, Payslip
    ).join(
        Payslip, Employee.id == Payslip.employee_id
    ).filter(
        Payslip.organization_id == current_org.id,
        Payslip.payroll_period_id.in_(period_ids)
    )

    if employee_id:
        query = query.filter(Employee.uuid == employee_id)
    if department_id:
        dept = db.query(Department).filter(Department.uuid == department_id).first()
        if dept:
            query = query.filter(Employee.department_id == dept.id)

    results = query.all()

    emp_data = {}
    for r in results:
        emp = r.Employee
        ps = r.Payslip
        
        if emp.id not in emp_data:
            emp_data[emp.id] = {
                "employee_uuid": emp.uuid,
                "employee_code": emp.employee_code,
                "employee_name": f"{emp.first_name} {emp.last_name}",
                "department": None,  # Will look up later or could join
                "dept_id": emp.department_id,
                "ytd_gross": Decimal('0'),
                "ytd_net": Decimal('0'),
                "ytd_deductions": Decimal('0'),
                "ytd_tax": Decimal('0'),
                "periods_count": 0,
                "monthly_breakdown": []
            }
            
        p = period_map[ps.payroll_period_id]
        
        gross = Decimal(str(ps.gross_salary))
        net = Decimal(str(ps.net_salary))
        ded = Decimal(str(ps.total_deductions))
        tax = Decimal(str(ps.tax_deducted))
        
        emp_data[emp.id]["ytd_gross"] += gross
        emp_data[emp.id]["ytd_net"] += net
        emp_data[emp.id]["ytd_deductions"] += ded
        emp_data[emp.id]["ytd_tax"] += tax
        emp_data[emp.id]["periods_count"] += 1
        
        emp_data[emp.id]["monthly_breakdown"].append({
            "period_name": p.period_name,
            "period_start_date": p.period_start_date,
            "gross": gross,
            "net": net,
            "deductions": ded,
            "tax_deducted": tax
        })

    # Resolve departments
    dept_ids = [d["dept_id"] for d in emp_data.values() if d["dept_id"] is not None]
    if dept_ids:
        depts = db.query(Department).filter(Department.id.in_(dept_ids)).all()
        dept_map = {d.id: d.department_name for d in depts}
        for emp_id in emp_data:
            if emp_data[emp_id]["dept_id"] in dept_map:
                emp_data[emp_id]["department"] = dept_map[emp_data[emp_id]["dept_id"]]

    data = list(emp_data.values())
    
    # Sort monthly breakdown by date
    for d in data:
        d["monthly_breakdown"].sort(key=lambda x: x["period_start_date"])

    return {
        "success": True,
        "message": "YTD earnings generated successfully",
        "financial_year": financial_year,
        "total_employees": len(data),
        "data": data
    }


@router.get("/payroll-cost-projection", response_model=PayrollCostProjectionResponse)
def get_payroll_cost_projection(
    months_ahead: int = Query(6, description="Number of months to project (1-12)"),
    include_increments: bool = Query(False, description="Whether to include projected increments"),
    db: Session = Depends(deps.get_db),
    current_org: Organization = Depends(deps.get_current_org),
    current_user: Union[Organization, Employee] = Depends(deps.get_current_user),
):
    _require_permission(db, current_user, PayrollReportPermissions.READ, "view payroll cost projection")
    
    if months_ahead < 1 or months_ahead > 24:
        raise HTTPException(status_code=400, detail="months_ahead must be between 1 and 24")

    # Find the most recent approved/processed/published payroll period
    latest_period = db.query(PayrollPeriod).filter(
        PayrollPeriod.organization_id == current_org.id,
        PayrollPeriod.status.in_(["approved", "processed", "published", "paid"])
    ).order_by(PayrollPeriod.period_start_date.desc()).first()

    if not latest_period:
        # Fallback to any period if none are approved
        latest_period = db.query(PayrollPeriod).filter(
            PayrollPeriod.organization_id == current_org.id
        ).order_by(PayrollPeriod.period_start_date.desc()).first()
        
    if not latest_period:
        raise HTTPException(status_code=404, detail="No historical payroll data found for projection")

    # Get baseline totals from the latest period
    baseline = db.query(
        func.count(func.distinct(Payslip.employee_id)).label("headcount"),
        func.coalesce(func.sum(Payslip.gross_salary), 0).label("gross"),
        func.coalesce(func.sum(Payslip.net_salary), 0).label("net"),
        func.coalesce(func.sum(Payslip.total_employer_contributions), 0).label("employer_contrib")
    ).filter(
        Payslip.organization_id == current_org.id,
        Payslip.payroll_period_id == latest_period.id
    ).first()

    base_headcount = baseline.headcount or 0
    base_gross = Decimal(str(baseline.gross))
    base_net = Decimal(str(baseline.net))
    base_employer_contrib = Decimal(str(baseline.employer_contrib))
    base_total_cost = base_gross + base_employer_contrib

    data = []
    
    # We will assume an annual increment of 5% (0.05) if include_increments is true, applied uniformly each month (compound)
    # E.g. monthly growth rate = 5% / 12
    annual_increment_pct = 5.0
    monthly_growth_rate = Decimal(str(annual_increment_pct / 100 / 12)) if include_increments else Decimal('0')

    import datetime
    from dateutil.relativedelta import relativedelta
    
    current_date = latest_period.period_start_date
    
    curr_headcount = base_headcount
    curr_gross = base_gross
    curr_net = base_net
    curr_employer_contrib = base_employer_contrib
    
    for i in range(1, months_ahead + 1):
        proj_date = current_date + relativedelta(months=i)
        
        if include_increments:
            curr_gross = curr_gross * (Decimal('1') + monthly_growth_rate)
            curr_net = curr_net * (Decimal('1') + monthly_growth_rate)
            curr_employer_contrib = curr_employer_contrib * (Decimal('1') + monthly_growth_rate)
            
        data.append({
            "month_label": proj_date.strftime("%b %Y"),
            "projection_date": proj_date,
            "projected_headcount": curr_headcount,
            "projected_gross": round(curr_gross, 2),
            "projected_net": round(curr_net, 2),
            "projected_employer_contributions": round(curr_employer_contrib, 2),
            "projected_total_cost": round(curr_gross + curr_employer_contrib, 2),
            "increment_applied": include_increments
        })

    return {
        "success": True,
        "message": "Payroll cost projection generated successfully",
        "base_month": latest_period.period_name,
        "months_ahead": months_ahead,
        "include_increments": include_increments,
        "annual_increment_rate_pct": annual_increment_pct if include_increments else 0.0,
        "base_headcount": base_headcount,
        "base_monthly_cost": base_total_cost,
        "data": data
    }
