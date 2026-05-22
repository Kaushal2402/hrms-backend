import uuid
from decimal import Decimal
from typing import Optional, Union

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.api import deps
from app.models.organization import Organization
from app.models.employee import Employee, Department, Location
from app.models.payroll import Payslip, PayrollPeriod
from app.schemas.payroll_reports import PayrollSummaryReportResponse
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
