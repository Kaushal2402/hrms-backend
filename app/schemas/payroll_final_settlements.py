from typing import List, Optional, Any
from datetime import date, datetime
from decimal import Decimal
from pydantic import BaseModel, UUID4
from app.schemas.department import PaginatedResponse
from app.schemas.employee import EmployeeSummarySchema
from app.models.payroll import FinalSettlement as FinalSettlementModel


class FinalSettlementBase(BaseModel):
    employee_uuid: UUID4
    last_working_date: date
    settlement_date: date
    separation_type: str
    notes: Optional[str] = None

class FinalSettlementCreate(FinalSettlementBase):
    pass

class FinalSettlementUpdate(BaseModel):
    last_working_date: Optional[date] = None
    settlement_date: Optional[date] = None
    separation_type: Optional[str] = None
    notes: Optional[str] = None
    earning_breakdown: Optional[dict] = None
    deduction_breakdown: Optional[dict] = None

class FinalSettlementSchema(FinalSettlementBase):
    uuid: UUID4
    settlement_number: str
    total_years: int
    total_months: int
    total_days: int
    last_month_salary: Decimal
    net_settlement_amount: Decimal
    status: str
    created_at: datetime
    updated_at: datetime
    employee: Optional[EmployeeSummarySchema] = None
    approval_comments: Optional[str] = None
    approved_at: Optional[datetime] = None
    paid_at: Optional[datetime] = None
    payment_mode: Optional[str] = None
    payment_reference: Optional[str] = None
    
    # Calculation & Dues
    leave_balance_days: Decimal
    leave_encashment_amount: Decimal
    notice_period_days: int
    notice_period_served: int
    notice_period_shortage: int
    notice_pay_recovery: Decimal
    is_gratuity_applicable: bool
    gratuity_amount: Decimal
    bonus_amount: Decimal
    pending_reimbursements: Decimal
    asset_recovery: Decimal
    loan_recovery: Decimal
    other_recoveries: Decimal
    total_recoveries: Decimal
    total_earnings: Decimal
    total_deductions: Decimal
    tax_deducted: Decimal

    class Config:
        from_attributes = True

class FinalSettlementResponse(BaseModel):
    success: bool
    message: str
    data: Optional[FinalSettlementSchema] = None

class FinalSettlementListResponse(PaginatedResponse[List[FinalSettlementSchema]]):
    pass

class SettlementApprovalUpdate(BaseModel):
    approval_comments: Optional[str] = None

class SettlementPaymentUpdate(BaseModel):
    payment_mode: str
    payment_reference: str