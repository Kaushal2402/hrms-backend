"""
Pydantic schemas for Payroll Reports & Analytics endpoints.
All monetary values are in the organization's base currency (INR by default).
"""
from __future__ import annotations

from typing import List, Optional, Dict, Any
from decimal import Decimal
from datetime import date
from pydantic import BaseModel, UUID4


# ---------------------------------------------------------------------------
# Shared / primitives
# ---------------------------------------------------------------------------

class _BaseResponse(BaseModel):
    success: bool
    message: str


# ---------------------------------------------------------------------------
# 1. Payroll Summary Report
# ---------------------------------------------------------------------------

class PayrollSummaryData(BaseModel):
    """Top-level totals and averages for a given payroll period/filter."""
    total_employees: int
    total_gross: Decimal
    total_net: Decimal
    total_deductions: Decimal
    total_employer_contributions: Decimal
    total_tax_deducted: Decimal
    total_lop_amount: Decimal
    total_arrears: Decimal
    total_one_time_payments: Decimal
    total_overtime_amount: Decimal
    total_reimbursements: Decimal
    average_gross: Decimal
    average_net: Decimal
    period_name: Optional[str] = None
    financial_year: Optional[str] = None


class PayrollSummaryReportResponse(_BaseResponse):
    data: PayrollSummaryData


# ---------------------------------------------------------------------------
# 2. Component-Wise Payroll Report
# ---------------------------------------------------------------------------

class ComponentWiseItem(BaseModel):
    component_id: int
    component_name: str
    component_type: str  # earning / deduction / employer_contribution
    total_amount: Decimal
    average_amount: Decimal
    employee_count: int


class ComponentWiseReportResponse(_BaseResponse):
    period_name: Optional[str] = None
    total_employees: int
    data: List[ComponentWiseItem]


# ---------------------------------------------------------------------------
# 3. Department-Wise Payroll Cost
# ---------------------------------------------------------------------------

class DepartmentWiseItem(BaseModel):
    department_id: Optional[int] = None
    department_name: str
    employee_count: int
    total_gross: Decimal
    total_net: Decimal
    total_employer_contributions: Decimal
    total_cost: Decimal  # gross + employer contributions


class DepartmentWiseReportResponse(_BaseResponse):
    period_name: Optional[str] = None
    financial_year: Optional[str] = None
    data: List[DepartmentWiseItem]


# ---------------------------------------------------------------------------
# 4. Payroll Variance Report
# ---------------------------------------------------------------------------

class VarianceItem(BaseModel):
    label: str  # e.g. "Total Gross", "Total Net", "Total Deductions", …
    current_value: Decimal
    previous_value: Decimal
    absolute_variance: Decimal
    percentage_variance: float  # can be +/-


class PayrollVarianceReportResponse(_BaseResponse):
    current_period_name: str
    compare_period_name: str
    current_employee_count: int
    previous_employee_count: int
    variance: List[VarianceItem]


# ---------------------------------------------------------------------------
# 5. Cost-Center Allocation Report
# ---------------------------------------------------------------------------

class CostCenterAllocationItem(BaseModel):
    cost_center_id: Optional[int] = None
    cost_center_name: str
    cost_center_code: Optional[str] = None
    employee_count: int
    total_gross: Decimal
    total_net: Decimal
    total_employer_contributions: Decimal
    total_cost: Decimal
    allocation_percentage: float  # % of organisation-wide total cost


class CostCenterAllocationResponse(_BaseResponse):
    period_name: Optional[str] = None
    total_org_cost: Decimal
    data: List[CostCenterAllocationItem]


# ---------------------------------------------------------------------------
# 6. Tax Deduction (TDS) Report
# ---------------------------------------------------------------------------

class TaxDeductionRecord(BaseModel):
    employee_uuid: UUID4
    employee_code: str
    employee_name: str
    department: Optional[str] = None
    pan_number: Optional[str] = None
    total_tds_deducted: Decimal
    total_gross_income: Decimal
    total_net_income: Decimal
    periods_included: int  # number of payroll periods counted


class TaxDeductionReportResponse(_BaseResponse):
    financial_year: str
    quarter: Optional[int] = None  # 1-4; None → full year
    total_tds: Decimal
    total_employees: int
    data: List[TaxDeductionRecord]


# ---------------------------------------------------------------------------
# 7. Loan Recovery Report
# ---------------------------------------------------------------------------

class LoanRecoveryRecord(BaseModel):
    employee_uuid: UUID4
    employee_code: str
    employee_name: str
    loan_number: str
    loan_type: str
    principal_recovered: Decimal
    interest_recovered: Decimal
    total_recovered: Decimal
    outstanding_balance: Decimal
    status: str  # loan status


class LoanRecoveryReportResponse(_BaseResponse):
    period_name: Optional[str] = None
    status_filter: Optional[str] = None
    total_recovered: Decimal
    data: List[LoanRecoveryRecord]


# ---------------------------------------------------------------------------
# 8. Salary Register
# ---------------------------------------------------------------------------

class SalaryRegisterComponent(BaseModel):
    component_name: str
    component_type: str
    amount: Decimal


class SalaryRegisterRecord(BaseModel):
    employee_uuid: UUID4
    employee_code: str
    employee_name: str
    department: Optional[str] = None
    location: Optional[str] = None
    designation: Optional[str] = None
    bank_account_number: Optional[str] = None
    ifsc_code: Optional[str] = None
    days_present: Decimal
    lop_days: Decimal
    gross_salary: Decimal
    total_deductions: Decimal
    net_salary: Decimal
    tax_deducted: Decimal
    components: List[SalaryRegisterComponent]


class SalaryRegisterReportResponse(_BaseResponse):
    period_name: Optional[str] = None
    total_employees: int
    format: str  # "json", "pdf", "excel"
    download_url: Optional[str] = None  # set when format != json
    data: List[SalaryRegisterRecord]


# ---------------------------------------------------------------------------
# 9. YTD Earnings Report
# ---------------------------------------------------------------------------

class YTDMonthlyBreakdown(BaseModel):
    period_name: str
    period_start_date: date
    gross: Decimal
    net: Decimal
    deductions: Decimal
    tax_deducted: Decimal


class YTDEarningsRecord(BaseModel):
    employee_uuid: UUID4
    employee_code: str
    employee_name: str
    department: Optional[str] = None
    ytd_gross: Decimal
    ytd_net: Decimal
    ytd_deductions: Decimal
    ytd_tax: Decimal
    periods_count: int
    monthly_breakdown: List[YTDMonthlyBreakdown]


class YTDEarningsReportResponse(_BaseResponse):
    financial_year: str
    total_employees: int
    data: List[YTDEarningsRecord]


# ---------------------------------------------------------------------------
# 10. Payroll Cost Projection
# ---------------------------------------------------------------------------

class ProjectionMonthData(BaseModel):
    month_label: str  # e.g. "Jun 2026"
    projection_date: date
    projected_headcount: int
    projected_gross: Decimal
    projected_net: Decimal
    projected_employer_contributions: Decimal
    projected_total_cost: Decimal
    increment_applied: bool


class PayrollCostProjectionResponse(_BaseResponse):
    base_month: str
    months_ahead: int
    include_increments: bool
    annual_increment_rate_pct: float
    base_headcount: int
    base_monthly_cost: Decimal
    data: List[ProjectionMonthData]
