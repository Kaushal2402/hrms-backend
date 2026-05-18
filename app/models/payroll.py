from sqlalchemy import Column, Integer, String, Boolean, DateTime, Text, Enum, Date, Numeric, ForeignKey, Index, JSON
from sqlalchemy.orm import relationship
from datetime import datetime
import uuid
import enum
from app.db.base_class import Base
from app.models.organization import GUID

# ============================================================================
# ENUMS
# ============================================================================

class PayFrequency(str, enum.Enum):
    MONTHLY = "monthly"
    BI_WEEKLY = "bi_weekly"
    WEEKLY = "weekly"
    SEMI_MONTHLY = "semi_monthly"
    QUARTERLY = "quarterly"

class ComponentType(str, enum.Enum):
    EARNING = "earning"
    DEDUCTION = "deduction"
    EMPLOYER_CONTRIBUTION = "employer_contribution"

class CalculationType(str, enum.Enum):
    FIXED = "fixed"
    PERCENTAGE = "percentage"
    FORMULA = "formula"
    ATTENDANCE_BASED = "attendance_based"
    PERFORMANCE_BASED = "performance_based"

class PayrollStatus(str, enum.Enum):
    DRAFT = "draft"
    IN_PROGRESS = "in_progress"
    PENDING_APPROVAL = "pending_approval"
    APPROVED = "approved"
    PROCESSED = "processed"
    PUBLISHED = "published"
    PAID = "paid"
    REVERSED = "reversed"
    ON_HOLD = "on_hold"

class PayslipStatus(str, enum.Enum):
    GENERATED = "generated"
    PUBLISHED = "published"
    SENT = "sent"
    VIEWED = "viewed"
    DOWNLOADED = "downloaded"

class LoanStatus(str, enum.Enum):
    PENDING = "pending"
    APPROVED = "approved"
    ACTIVE = "active"
    COMPLETED = "completed"
    REJECTED = "rejected"
    WRITTEN_OFF = "written_off"

class ReimbursementStatus(str, enum.Enum):
    DRAFT = "draft"
    SUBMITTED = "submitted"
    APPROVED = "approved"
    REJECTED = "rejected"
    PAID = "paid"

class TaxRegime(str, enum.Enum):
    OLD = "old"
    NEW = "new"
    DEFAULT = "default"


# ============================================================================
# SALARY STRUCTURE & COMPONENTS
# ============================================================================

class SalaryComponent(Base):
    """Master salary components (Basic, HRA, DA, etc.)"""
    __tablename__ = "salary_components"
    
    id = Column(Integer, primary_key=True, index=True)
    uuid = Column(GUID(), default=uuid.uuid4, unique=True, nullable=False, index=True)
    organization_id = Column(Integer, ForeignKey('organization.id'), nullable=False, index=True)
    
    # Component Details
    component_code = Column(String(50), nullable=False, index=True)
    component_name = Column(String(150), nullable=False)
    component_type = Column(Enum(ComponentType), nullable=False)
    description = Column(Text, nullable=True)
    
    # Calculation
    calculation_type = Column(Enum(CalculationType), nullable=False)
    calculation_value = Column(Numeric(15, 2), nullable=True)  # For fixed or percentage
    calculation_formula = Column(Text, nullable=True)  # For formula-based
    # Example formula: "(BASIC * 0.4) + (DA * 0.5)"
    
    # Based On (for percentage calculation)
    based_on_component_ids = Column(JSON, nullable=True)  # Component IDs
    
    # Tax & Statutory
    is_taxable = Column(Boolean, default=True)
    is_part_of_gross = Column(Boolean, default=True)
    is_part_of_ctc = Column(Boolean, default=True)
    exemption_limit = Column(Numeric(12, 2), nullable=True)
    
    # Statutory Contributions
    has_employer_contribution = Column(Boolean, default=False)
    employer_contribution_percentage = Column(Numeric(5, 2), nullable=True)
    has_employee_contribution = Column(Boolean, default=False)
    employee_contribution_percentage = Column(Numeric(5, 2), nullable=True)
    
    # Display
    display_order = Column(Integer, default=0)
    show_on_payslip = Column(Boolean, default=True)
    
    # Applicability
    applicable_to_employee_types = Column(JSON, nullable=True)
    min_salary_for_applicability = Column(Numeric(12, 2), nullable=True)
    
    # Frequency Override
    pay_frequency_override = Column(Enum(PayFrequency), nullable=True)
    
    # Proration
    is_prorated = Column(Boolean, default=True)
    proration_based_on = Column(String(20), nullable=True)  # 'days', 'hours'
    
    # Compliance
    statutory_component_type = Column(String(50), nullable=True)
    # 'epf', 'esi', 'professional_tax', 'tds', 'gratuity', etc.
    
    is_active = Column(Boolean, default=True, index=True)
    
    # Audit
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    created_by = Column(Integer, ForeignKey('employees.id'), nullable=True)
    
    __table_args__ = (
        Index('idx_sal_comp_org_code', 'organization_id', 'component_code', unique=True),
    )


class SalaryTemplate(Base):
    """Salary structure templates"""
    __tablename__ = "salary_templates"
    
    id = Column(Integer, primary_key=True, index=True)
    uuid = Column(GUID(), default=uuid.uuid4, unique=True, nullable=False, index=True)
    organization_id = Column(Integer, ForeignKey('organization.id'), nullable=False, index=True)
    
    template_code = Column(String(50), nullable=False)
    template_name = Column(String(150), nullable=False)
    description = Column(Text, nullable=True)
    
    # Applicability
    applicable_to = Column(String(50), nullable=True)  # 'all', 'grade', 'department', 'location'
    grade_ids = Column(JSON, nullable=True)
    department_ids = Column(JSON, nullable=True)
    location_ids = Column(JSON, nullable=True)
    employment_types = Column(JSON, nullable=True)
    
    # CTC Calculation
    annual_ctc_min = Column(Numeric(15, 2), nullable=True)
    annual_ctc_max = Column(Numeric(15, 2), nullable=True)
    
    # Pay Frequency
    pay_frequency = Column(Enum(PayFrequency), default=PayFrequency.MONTHLY, nullable=False)
    
    is_active = Column(Boolean, default=True)
    is_default = Column(Boolean, default=False)
    
    # Effective Dates
    effective_from = Column(Date, nullable=False)
    effective_to = Column(Date, nullable=True)
    
    # Audit
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    created_by = Column(Integer, ForeignKey('employees.id'), nullable=True)
    
    # Relationships
    components = relationship("SalaryTemplateComponent", cascade="all, delete-orphan")
    
    __table_args__ = (
        Index('idx_sal_template_org_code', 'organization_id', 'template_code', unique=True),
    )


class SalaryTemplateComponent(Base):
    """Components in salary template"""
    __tablename__ = "salary_template_components"
    
    id = Column(Integer, primary_key=True, index=True)
    template_id = Column(Integer, ForeignKey('salary_templates.id'), nullable=False, index=True)
    component_id = Column(Integer, ForeignKey('salary_components.id'), nullable=False)
    
    # Override Calculation (if different from master)
    calculation_type_override = Column(Enum(CalculationType), nullable=True)
    calculation_value_override = Column(Numeric(15, 2), nullable=True)
    formula_override = Column(Text, nullable=True)
    
    # Min/Max Limits
    min_value = Column(Numeric(12, 2), nullable=True)
    max_value = Column(Numeric(12, 2), nullable=True)
    
    # Display Order
    display_order = Column(Integer, default=0)
    
    is_mandatory = Column(Boolean, default=True)
    is_active = Column(Boolean, default=True)
    
    created_at = Column(DateTime, default=datetime.utcnow)
    
    __table_args__ = (
        Index('idx_template_comp', 'template_id', 'component_id', unique=True),
    )


# ============================================================================
# EMPLOYEE SALARY ASSIGNMENT
# ============================================================================

class EmployeeSalary(Base):
    """Individual employee salary structure"""
    __tablename__ = "employee_salaries"
    
    id = Column(Integer, primary_key=True, index=True)
    uuid = Column(GUID(), default=uuid.uuid4, unique=True, nullable=False, index=True)
    organization_id = Column(Integer, ForeignKey('organization.id'), nullable=False, index=True)
    
    employee_id = Column(Integer, ForeignKey('employees.id'), nullable=False, index=True)
    template_id = Column(Integer, ForeignKey('salary_templates.id'), nullable=True)
    
    # CTC Details
    annual_ctc = Column(Numeric(15, 2), nullable=False)
    monthly_ctc = Column(Numeric(12, 2), nullable=False)
    
    # Gross & Net
    monthly_gross = Column(Numeric(12, 2), nullable=False)
    monthly_net = Column(Numeric(12, 2), nullable=False)
    
    # Pay Frequency
    pay_frequency = Column(Enum(PayFrequency), default=PayFrequency.MONTHLY, nullable=False)
    
    # Currency
    currency = Column(String(3), default='INR', nullable=False)
    
    # Bank Details
    bank_account_id = Column(Integer, ForeignKey('employee_bank_accounts.id'), nullable=True)
    
    # Payment Mode
    payment_mode = Column(String(20), default='bank_transfer')  # 'bank_transfer', 'cash', 'cheque'
    
    # Effective Dates
    effective_from = Column(Date, nullable=False, index=True)
    effective_to = Column(Date, nullable=True, index=True)
    
    # Revision Info
    revision_number = Column(Integer, default=1)
    previous_salary_id = Column(Integer, ForeignKey('employee_salaries.id'), nullable=True)
    revision_reason = Column(String(100), nullable=True)  # 'increment', 'promotion', 'correction'
    revision_percentage = Column(Numeric(5, 2), nullable=True)
    
    # Hold Salary
    is_on_hold = Column(Boolean, default=False, index=True)
    hold_reason = Column(Text, nullable=True)
    hold_from_date = Column(Date, nullable=True)
    
    # Status
    is_active = Column(Boolean, default=True, index=True)
    
    # Audit
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    created_by = Column(Integer, ForeignKey('employees.id'), nullable=True)
    approved_by = Column(Integer, ForeignKey('employees.id'), nullable=True)
    approved_at = Column(DateTime, nullable=True)
    
    __table_args__ = (
        Index('idx_emp_sal_emp_active', 'employee_id', 'is_active'),
        Index('idx_emp_sal_effective', 'employee_id', 'effective_from', 'effective_to'),
    )

    # Relationships
    employee = relationship("Employee", foreign_keys=[employee_id], backref="salaries")
    salary_template = relationship("SalaryTemplate", foreign_keys=[template_id], backref="assigned_salaries")
    bank_account = relationship("EmployeeBankAccount", foreign_keys=[bank_account_id])


class EmployeeSalaryComponent(Base):
    """Individual salary components for employee"""
    __tablename__ = "employee_salary_components"
    
    id = Column(Integer, primary_key=True, index=True)
    employee_salary_id = Column(Integer, ForeignKey('employee_salaries.id'), nullable=False, index=True)
    component_id = Column(Integer, ForeignKey('salary_components.id'), nullable=False)
    
    # Amount Details
    monthly_amount = Column(Numeric(12, 2), nullable=False)
    annual_amount = Column(Numeric(15, 2), nullable=False)
    
    # Calculation Details (stored for audit)
    calculation_type = Column(Enum(CalculationType), nullable=False)
    calculation_value = Column(Numeric(15, 2), nullable=True)
    calculation_formula = Column(Text, nullable=True)
    calculated_on = Column(JSON, nullable=True)  # Which components it was based on
    
    # Override
    is_override = Column(Boolean, default=False)
    override_reason = Column(Text, nullable=True)
    
    # Display
    display_order = Column(Integer, default=0)
    
    created_at = Column(DateTime, default=datetime.utcnow)
    
    __table_args__ = (
        Index('idx_emp_sal_comp', 'employee_salary_id', 'component_id'),
    )


# ============================================================================
# PAYROLL PERIODS & PROCESSING
# ============================================================================

class PayrollPeriod(Base):
    """Payroll processing periods"""
    __tablename__ = "payroll_periods"
    
    id = Column(Integer, primary_key=True, index=True)
    uuid = Column(GUID(), default=uuid.uuid4, unique=True, nullable=False, index=True)
    organization_id = Column(Integer, ForeignKey('organization.id'), nullable=False, index=True)
    
    period_name = Column(String(100), nullable=False)  # "January 2024", "Week 1 - Jan 2024"
    period_code = Column(String(50), nullable=False)  # "2024-01", "2024-W01"
    
    # Period Dates
    period_start_date = Column(Date, nullable=False, index=True)
    period_end_date = Column(Date, nullable=False, index=True)
    
    # Payment Date
    payment_date = Column(Date, nullable=False)
    
    # Pay Frequency
    pay_frequency = Column(Enum(PayFrequency), nullable=False)
    
    # Working Days
    total_working_days = Column(Integer, nullable=False)
    
    # Financial Year
    financial_year = Column(String(20), nullable=False)  # "FY 2024-25"
    
    # Status
    status = Column(Enum(PayrollStatus), default=PayrollStatus.DRAFT, nullable=False, index=True)
    
    # Processing
    processing_started_at = Column(DateTime, nullable=True)
    processing_completed_at = Column(DateTime, nullable=True)
    processed_by = Column(Integer, ForeignKey('employees.id'), nullable=True)
    
    # Approval
    submitted_for_approval_at = Column(DateTime, nullable=True)
    submitted_by = Column(Integer, ForeignKey('employees.id'), nullable=True)
    approved_at = Column(DateTime, nullable=True)
    approved_by = Column(Integer, ForeignKey('employees.id'), nullable=True)
    approval_comments = Column(Text, nullable=True)
    
    # Publishing
    published_at = Column(DateTime, nullable=True)
    published_by = Column(Integer, ForeignKey('employees.id'), nullable=True)
    
    # Payment Processing
    payment_processed_at = Column(DateTime, nullable=True)
    payment_processed_by = Column(Integer, ForeignKey('employees.id'), nullable=True)
    payment_reference = Column(String(100), nullable=True)
    
    # Summary
    total_employees = Column(Integer, default=0)
    total_gross_amount = Column(Numeric(15, 2), default=0)
    total_deductions = Column(Numeric(15, 2), default=0)
    total_net_amount = Column(Numeric(15, 2), default=0)
    total_employer_contributions = Column(Numeric(15, 2), default=0)
    
    # Hold
    is_on_hold = Column(Boolean, default=False)
    hold_reason = Column(Text, nullable=True)
    
    # Lock
    is_locked = Column(Boolean, default=False, index=True)
    locked_at = Column(DateTime, nullable=True)
    locked_by = Column(Integer, ForeignKey('employees.id'), nullable=True)
    
    # Notes
    notes = Column(Text, nullable=True)
    
    # Audit
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    created_by = Column(Integer, ForeignKey('employees.id'), nullable=True)
    
    __table_args__ = (
        Index('idx_payroll_period_org_code', 'organization_id', 'period_code', unique=True),
        Index('idx_payroll_period_dates', 'period_start_date', 'period_end_date'),
        Index('idx_payroll_period_status', 'organization_id', 'status'),
    )


class Payslip(Base):
    """Individual employee payslips"""
    __tablename__ = "payslips"
    
    id = Column(Integer, primary_key=True, index=True)
    uuid = Column(GUID(), default=uuid.uuid4, unique=True, nullable=False, index=True)
    organization_id = Column(Integer, ForeignKey('organization.id'), nullable=False, index=True)
    
    payroll_period_id = Column(Integer, ForeignKey('payroll_periods.id'), nullable=False, index=True)
    employee_id = Column(Integer, ForeignKey('employees.id'), nullable=False, index=True)
    employee_salary_id = Column(Integer, ForeignKey('employee_salaries.id'), nullable=False)
    
    # Payslip Number
    payslip_number = Column(String(50), nullable=False, unique=True, index=True)
    
    # Period Details
    period_start_date = Column(Date, nullable=False)
    period_end_date = Column(Date, nullable=False)
    payment_date = Column(Date, nullable=False)
    
    # Days Calculation
    total_working_days = Column(Integer, nullable=False)
    days_present = Column(Numeric(5, 2), nullable=False)
    days_absent = Column(Numeric(5, 2), default=0)
    days_on_leave = Column(Numeric(5, 2), default=0)
    paid_days = Column(Numeric(5, 2), nullable=False)
    
    # LOP (Loss of Pay)
    lop_days = Column(Numeric(5, 2), default=0)
    lop_amount = Column(Numeric(12, 2), default=0)
    
    # Salary Calculation
    basic_salary = Column(Numeric(12, 2), nullable=False)
    gross_salary = Column(Numeric(12, 2), nullable=False)
    total_earnings = Column(Numeric(12, 2), nullable=False)
    total_deductions = Column(Numeric(12, 2), nullable=False)
    net_salary = Column(Numeric(12, 2), nullable=False)
    
    # Employer Contributions
    total_employer_contributions = Column(Numeric(12, 2), default=0)
    
    # CTC for the month
    monthly_ctc = Column(Numeric(12, 2), nullable=False)
    
    # Arrears
    arrears_amount = Column(Numeric(12, 2), default=0)
    arrears_description = Column(Text, nullable=True)
    
    # One-time Payments
    one_time_payments = Column(Numeric(12, 2), default=0)
    one_time_description = Column(Text, nullable=True)
    
    # Overtime
    overtime_hours = Column(Numeric(6, 2), default=0)
    overtime_amount = Column(Numeric(10, 2), default=0)
    
    # Reimbursements
    total_reimbursements = Column(Numeric(10, 2), default=0)
    
    # Tax
    tax_deducted = Column(Numeric(10, 2), default=0)
    
    # Cumulative YTD (Year-to-Date)
    ytd_gross = Column(Numeric(15, 2), nullable=True)
    ytd_deductions = Column(Numeric(15, 2), nullable=True)
    ytd_net = Column(Numeric(15, 2), nullable=True)
    ytd_tax = Column(Numeric(15, 2), nullable=True)
    
    # Payment Details
    bank_account_id = Column(Integer, ForeignKey('employee_bank_accounts.id'), nullable=True)
    payment_mode = Column(String(20), nullable=True)
    
    # Status
    status = Column(Enum(PayslipStatus), default=PayslipStatus.GENERATED, nullable=False, index=True)
    
    # Publishing
    is_published = Column(Boolean, default=False, index=True)
    published_at = Column(DateTime, nullable=True)
    
    # Employee Access
    first_viewed_at = Column(DateTime, nullable=True)
    view_count = Column(Integer, default=0)
    downloaded_at = Column(DateTime, nullable=True)
    download_count = Column(Integer, default=0)
    
    # Email
    email_sent = Column(Boolean, default=False)
    email_sent_at = Column(DateTime, nullable=True)
    
    # Hold
    is_on_hold = Column(Boolean, default=False, index=True)
    hold_reason = Column(Text, nullable=True)
    
    # Payslip Document
    payslip_pdf_url = Column(String(500), nullable=True)
    
    # Reversal
    is_reversed = Column(Boolean, default=False)
    reversed_at = Column(DateTime, nullable=True)
    reversed_by = Column(Integer, ForeignKey('employees.id'), nullable=True)
    reversal_reason = Column(Text, nullable=True)
    reversed_payslip_id = Column(Integer, ForeignKey('payslips.id'), nullable=True)
    
    # Notes
    notes = Column(Text, nullable=True)
    
    # Audit
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    created_by = Column(Integer, ForeignKey('employees.id'), nullable=True)
    
    __table_args__ = (
        Index('idx_payslip_period_emp', 'payroll_period_id', 'employee_id', unique=True),
        Index('idx_payslip_emp_period', 'employee_id', 'period_start_date'),
        Index('idx_payslip_status', 'organization_id', 'status'),
    )


class PayslipComponent(Base):
    """Individual components in payslip"""
    __tablename__ = "payslip_components"
    
    id = Column(Integer, primary_key=True, index=True)
    payslip_id = Column(Integer, ForeignKey('payslips.id'), nullable=False, index=True)
    component_id = Column(Integer, ForeignKey('salary_components.id'), nullable=False)
    
    component_name = Column(String(150), nullable=False)  # Stored for historical accuracy
    component_type = Column(Enum(ComponentType), nullable=False)
    
    # Calculation
    monthly_amount = Column(Numeric(12, 2), nullable=False)  # From salary structure
    actual_amount = Column(Numeric(12, 2), nullable=False)  # After proration/adjustments
    
    # Proration
    is_prorated = Column(Boolean, default=False)
    proration_days = Column(Numeric(5, 2), nullable=True)
    proration_percentage = Column(Numeric(5, 2), nullable=True)
    
    # YTD
    ytd_amount = Column(Numeric(15, 2), nullable=True)
    
    # Display
    display_order = Column(Integer, default=0)
    
    # Calculation Details (for audit)
    calculation_details = Column(JSON, nullable=True)
    
    created_at = Column(DateTime, default=datetime.utcnow)


# ============================================================================
# LOANS & ADVANCES
# ============================================================================

class EmployeeLoan(Base):
    """Employee loans and advances"""
    __tablename__ = "employee_loans"
    
    id = Column(Integer, primary_key=True, index=True)
    uuid = Column(GUID(), default=uuid.uuid4, unique=True, nullable=False, index=True)
    organization_id = Column(Integer, ForeignKey('organization.id'), nullable=False, index=True)
    
    employee_id = Column(Integer, ForeignKey('employees.id'), nullable=False, index=True)
    
    # Loan Details
    loan_type = Column(String(50), nullable=False)  # 'personal_loan', 'advance', 'emergency_loan'
    loan_number = Column(String(50), nullable=False, unique=True, index=True)
    
    # Amount
    loan_amount = Column(Numeric(12, 2), nullable=False)
    interest_rate = Column(Numeric(5, 2), default=0)
    total_payable = Column(Numeric(12, 2), nullable=False)
    
    # Repayment
    repayment_start_date = Column(Date, nullable=False)
    number_of_installments = Column(Integer, nullable=False)
    monthly_installment = Column(Numeric(10, 2), nullable=False)
    
    installments_paid = Column(Integer, default=0)
    amount_paid = Column(Numeric(12, 2), default=0)
    outstanding_amount = Column(Numeric(12, 2), nullable=False)
    
    # Purpose
    purpose = Column(Text, nullable=False)
    
    # Approval
    status = Column(Enum(LoanStatus), default=LoanStatus.PENDING, nullable=False, index=True)
    approved_by = Column(Integer, ForeignKey('employees.id'), nullable=True)
    approved_at = Column(DateTime, nullable=True)
    approval_comments = Column(Text, nullable=True)
    
    rejection_reason = Column(Text, nullable=True)
    rejected_at = Column(DateTime, nullable=True)
    
    # Disbursement
    disbursement_date = Column(Date, nullable=True)
    disbursement_mode = Column(String(20), nullable=True)  # 'salary', 'bank_transfer', 'cash'
    disbursement_reference = Column(String(100), nullable=True)
    
    # Completion
    completed_at = Column(DateTime, nullable=True)
    
    # Guarantor (optional)
    guarantor_employee_id = Column(Integer, ForeignKey('employees.id'), nullable=True)
    
    # Documents
    attachment_urls = Column(JSON, nullable=True)
    
    # Notes
    notes = Column(Text, nullable=True)
    
    # Audit
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    created_by = Column(Integer, ForeignKey('employees.id'), nullable=True)
    
    employee = relationship("Employee", foreign_keys=[employee_id])
    
    @property
    def employee_uuid(self):
        return self.employee.uuid if self.employee else None
    
    __table_args__ = (
        Index('idx_loan_emp_status', 'employee_id', 'status'),
    )


class LoanRepayment(Base):
    """Loan repayment schedule and tracking"""
    __tablename__ = "loan_repayments"
    
    id = Column(Integer, primary_key=True, index=True)
    loan_id = Column(Integer, ForeignKey('employee_loans.id'), nullable=False, index=True)
    
    installment_number = Column(Integer, nullable=False)
    due_date = Column(Date, nullable=False, index=True)
    
    # Amount Details
    principal_amount = Column(Numeric(10, 2), nullable=False)
    interest_amount = Column(Numeric(10, 2), default=0)
    total_amount = Column(Numeric(10, 2), nullable=False)
    
    # Payment
    is_paid = Column(Boolean, default=False, index=True)
    paid_date = Column(Date, nullable=True)
    paid_amount = Column(Numeric(10, 2), default=0)
    
    # Payroll Integration
    payslip_id = Column(Integer, ForeignKey('payslips.id'), nullable=True)
    payroll_period_id = Column(Integer, ForeignKey('payroll_periods.id'), nullable=True)
    
    # Balance
    outstanding_balance_after_payment = Column(Numeric(12, 2), nullable=True)
    
    # Notes
    notes = Column(Text, nullable=True)
    
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    __table_args__ = (
        Index('idx_loan_repay_due', 'loan_id', 'due_date'),
        Index('idx_loan_repay_status', 'is_paid', 'due_date'),
    )


# ============================================================================
# REIMBURSEMENTS
# ============================================================================

class ReimbursementCategory(Base):
    """Reimbursement categories"""
    __tablename__ = "reimbursement_categories"
    
    id = Column(Integer, primary_key=True, index=True)
    uuid = Column(GUID(), default=uuid.uuid4, unique=True, nullable=False)
    organization_id = Column(Integer, ForeignKey('organization.id'), nullable=False, index=True)
    
    category_code = Column(String(50), nullable=False)
    category_name = Column(String(150), nullable=False)
    description = Column(Text, nullable=True)
    
    # Limits
    max_claim_per_month = Column(Numeric(10, 2), nullable=True)
    max_claim_per_year = Column(Numeric(12, 2), nullable=True)
    max_claim_per_transaction = Column(Numeric(10, 2), nullable=True)
    
    # Approval
    requires_approval = Column(Boolean, default=True)
    approval_limit = Column(Numeric(10, 2), nullable=True)  # Auto-approve below this
    
    # Documentation
    requires_receipt = Column(Boolean, default=True)
    receipt_mandatory_above = Column(Numeric(8, 2), nullable=True)
    
    # Tax
    is_taxable = Column(Boolean, default=False)
    
    # Applicability
    applicable_to_employee_types = Column(JSON, nullable=True)
    
    is_active = Column(Boolean, default=True)
    
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    __table_args__ = (
        Index('idx_reimb_cat_org_code', 'organization_id', 'category_code', unique=True),
    )


class ReimbursementClaim(Base):
    """Employee reimbursement claims"""
    __tablename__ = "reimbursement_claims"
    
    id = Column(Integer, primary_key=True, index=True)
    uuid = Column(GUID(), default=uuid.uuid4, unique=True, nullable=False, index=True)
    organization_id = Column(Integer, ForeignKey('organization.id'), nullable=False, index=True)
    
    employee_id = Column(Integer, ForeignKey('employees.id'), nullable=False, index=True)
    category_id = Column(Integer, ForeignKey('reimbursement_categories.id'), nullable=False)
    
    claim_number = Column(String(50), nullable=False, unique=True, index=True)
    claim_date = Column(Date, default=datetime.utcnow, nullable=False)
    
    # Amount
    claimed_amount = Column(Numeric(10, 2), nullable=False)
    approved_amount = Column(Numeric(10, 2), nullable=True)
    
    # Details
    expense_date = Column(Date, nullable=False)
    description = Column(Text, nullable=False)
    merchant_name = Column(String(200), nullable=True)
    
    # Receipts
    receipt_urls = Column(JSON, nullable=True)
    receipt_numbers = Column(JSON, nullable=True)
    
    # Approval
    status = Column(Enum(ReimbursementStatus), default=ReimbursementStatus.DRAFT, nullable=False, index=True)
    
    submitted_at = Column(DateTime, nullable=True)
    
    approver_id = Column(Integer, ForeignKey('employees.id'), nullable=True, index=True)
    approved_at = Column(DateTime, nullable=True)
    approver_comments = Column(Text, nullable=True)
    
    rejection_reason = Column(Text, nullable=True)
    rejected_at = Column(DateTime, nullable=True)
    
    # Payment
    payslip_id = Column(Integer, ForeignKey('payslips.id'), nullable=True)
    payroll_period_id = Column(Integer, ForeignKey('payroll_periods.id'), nullable=True)
    paid_at = Column(DateTime, nullable=True)
    payment_reference = Column(String(100), nullable=True)
    
    # Notes
    notes = Column(Text, nullable=True)
    
    # Relationships
    category = relationship("ReimbursementCategory", foreign_keys=[category_id])
    employee = relationship("Employee", foreign_keys=[employee_id])
    approver = relationship("Employee", foreign_keys=[approver_id])
    
    # Audit
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    __table_args__ = (
        Index('idx_reimb_claim_emp_status', 'employee_id', 'status'),
        Index('idx_reimb_claim_approver', 'approver_id', 'status'),
    )


# ============================================================================
# FINAL SETTLEMENT
# ============================================================================

class FinalSettlement(Base):
    """Final settlement calculation for separated employees"""
    __tablename__ = "final_settlements"
    
    id = Column(Integer, primary_key=True, index=True)
    uuid = Column(GUID(), default=uuid.uuid4, unique=True, nullable=False, index=True)
    organization_id = Column(Integer, ForeignKey('organization.id'), nullable=False, index=True)
    
    employee_id = Column(Integer, ForeignKey('employees.id'), nullable=False, unique=True, index=True)
    
    settlement_number = Column(String(50), nullable=False, unique=True, index=True)
    
    # Separation Details
    last_working_date = Column(Date, nullable=False)
    settlement_date = Column(Date, nullable=False)
    separation_type = Column(String(50), nullable=False)  # 'resignation', 'termination', 'retirement'
    
    # Working Period
    total_years = Column(Integer, nullable=False)
    total_months = Column(Integer, nullable=False)
    total_days = Column(Integer, nullable=False)
    
    # Last Salary
    last_month_days_worked = Column(Integer, nullable=False)
    last_month_salary = Column(Numeric(12, 2), nullable=False)
    
    # Leave Encashment
    leave_balance_days = Column(Numeric(6, 2), nullable=False)
    leave_encashment_amount = Column(Numeric(12, 2), default=0)
    
    # Notice Period
    notice_period_days = Column(Integer, nullable=False)
    notice_period_served = Column(Integer, nullable=False)
    notice_period_shortage = Column(Integer, default=0)
    notice_pay_recovery = Column(Numeric(10, 2), default=0)
    
    # Gratuity
    is_gratuity_applicable = Column(Boolean, default=False)
    gratuity_amount = Column(Numeric(12, 2), default=0)
    
    # Bonus
    bonus_amount = Column(Numeric(10, 2), default=0)
    
    # Pending Reimbursements
    pending_reimbursements = Column(Numeric(10, 2), default=0)
    
    # Recoveries
    asset_recovery = Column(Numeric(10, 2), default=0)
    loan_recovery = Column(Numeric(10, 2), default=0)
    other_recoveries = Column(Numeric(10, 2), default=0)
    total_recoveries = Column(Numeric(12, 2), default=0)
    
    # Calculation
    total_earnings = Column(Numeric(12, 2), nullable=False)
    total_deductions = Column(Numeric(12, 2), nullable=False)
    net_settlement_amount = Column(Numeric(12, 2), nullable=False)
    
    # Tax
    tax_deducted = Column(Numeric(10, 2), default=0)
    
    # Approval
    status = Column(String(20), default='draft', nullable=False, index=True)
    # 'draft', 'pending_approval', 'approved', 'paid'
    
    approved_by = Column(Integer, ForeignKey('employees.id'), nullable=True)
    approved_at = Column(DateTime, nullable=True)
    approval_comments = Column(Text, nullable=True)
    
    # Payment
    paid_at = Column(DateTime, nullable=True)
    payment_mode = Column(String(20), nullable=True)
    payment_reference = Column(String(100), nullable=True)
    
    # Documents
    settlement_letter_url = Column(String(500), nullable=True)
    calculation_sheet_url = Column(String(500), nullable=True)
    
    # Breakdown Details (JSON)
    earning_breakdown = Column(JSON, nullable=True)
    deduction_breakdown = Column(JSON, nullable=True)
    
    # Notes
    notes = Column(Text, nullable=True)
    
    # Audit
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    created_by = Column(Integer, ForeignKey('employees.id'), nullable=True)

    employee = relationship("Employee", foreign_keys=[employee_id])

    @property
    def employee_uuid(self):
        return self.employee.uuid if self.employee else None




# ============================================================================
# ARREARS & ONE-TIME PAYMENTS
# ============================================================================

class Arrear(Base):
    """Arrear payments"""
    __tablename__ = "arrears"
    
    id = Column(Integer, primary_key=True, index=True)
    uuid = Column(GUID(), default=uuid.uuid4, unique=True, nullable=False, index=True)
    organization_id = Column(Integer, ForeignKey('organization.id'), nullable=False, index=True)
    
    employee_id = Column(Integer, ForeignKey('employees.id'), nullable=False, index=True)
    
    arrear_number = Column(String(50), nullable=False, unique=True)
    arrear_type = Column(String(50), nullable=False)  # 'salary_revision', 'missed_component', 'bonus'
    
    # Period
    arrear_from_date = Column(Date, nullable=False)
    arrear_to_date = Column(Date, nullable=False)
    number_of_months = Column(Integer, nullable=False)
    
    # Amount
    arrear_amount = Column(Numeric(12, 2), nullable=False)
    
    # Tax Treatment
    is_taxable = Column(Boolean, default=True)
    tax_deducted = Column(Numeric(10, 2), default=0)
    
    # Reason
    reason = Column(Text, nullable=False)
    description = Column(Text, nullable=True)
    
    # Approval
    status = Column(String(20), default='pending', nullable=False, index=True)
    approved_by = Column(Integer, ForeignKey('employees.id'), nullable=True)
    approved_at = Column(DateTime, nullable=True)
    
    # Payment
    payslip_id = Column(Integer, ForeignKey('payslips.id'), nullable=True)
    payroll_period_id = Column(Integer, ForeignKey('payroll_periods.id'), nullable=True)
    paid_at = Column(DateTime, nullable=True)
    
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    created_by = Column(Integer, ForeignKey('employees.id'), nullable=True)

    employee = relationship("Employee", foreign_keys=[employee_id])


class OneTimePayment(Base):
    """One-time payments (bonus, incentive, award)"""
    __tablename__ = "one_time_payments"
    
    id = Column(Integer, primary_key=True, index=True)
    uuid = Column(GUID(), default=uuid.uuid4, unique=True, nullable=False, index=True)
    organization_id = Column(Integer, ForeignKey('organization.id'), nullable=False, index=True)
    
    employee_id = Column(Integer, ForeignKey('employees.id'), nullable=False, index=True)
    
    payment_number = Column(String(50), nullable=False, unique=True)
    payment_type = Column(String(50), nullable=False)
    # 'bonus', 'incentive', 'award', 'gift', 'performance_bonus', 'referral_bonus'

    payment_name = Column(String(150), nullable=False)

    # Amount
    payment_amount = Column(Numeric(12, 2), nullable=False)

    # Tax
    is_taxable = Column(Boolean, default=True)
    tax_deducted = Column(Numeric(10, 2), default=0)

    # Details
    description = Column(Text, nullable=True)
    payment_reason = Column(Text, nullable=True)

    # Approval
    status = Column(String(20), default='pending', nullable=False, index=True)
    approved_by = Column(Integer, ForeignKey('employees.id'), nullable=True)
    approved_at = Column(DateTime, nullable=True)

    # Payment
    payslip_id = Column(Integer, ForeignKey('payslips.id'), nullable=True)
    payroll_period_id = Column(Integer, ForeignKey('payroll_periods.id'), nullable=True)
    paid_at = Column(DateTime, nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    created_by = Column(Integer, ForeignKey('employees.id'), nullable=True)

    employee = relationship("Employee", foreign_keys=[employee_id])


# ============================================================================
# TAX DECLARATIONS & CALCULATIONS
# ============================================================================

class TaxDeclaration(Base):
    """Employee tax investment declarations"""
    __tablename__ = "tax_declarations"
    
    id = Column(Integer, primary_key=True, index=True)
    uuid = Column(GUID(), default=uuid.uuid4, unique=True, nullable=False, index=True)
    organization_id = Column(Integer, ForeignKey('organization.id'), nullable=False, index=True)
    
    employee_id = Column(Integer, ForeignKey('employees.id'), nullable=False, index=True)
    financial_year = Column(String(20), nullable=False)  # "FY 2024-25"
    
    # Tax Regime Choice
    tax_regime = Column(Enum(TaxRegime), default=TaxRegime.OLD, nullable=False)
    
    # Declaration Type
    declaration_type = Column(String(20), nullable=False)  # 'interim', 'final', 'revised'
    
    # Status
    status = Column(String(20), default='draft', nullable=False, index=True)
    # 'draft', 'submitted', 'under_review', 'approved', 'rejected'
    
    # Submission
    submitted_at = Column(DateTime, nullable=True)
    
    # Approval
    reviewed_by = Column(Integer, ForeignKey('employees.id'), nullable=True)
    reviewed_at = Column(DateTime, nullable=True)
    reviewer_comments = Column(Text, nullable=True)
    
    # Proof Submission
    proofs_submitted = Column(Boolean, default=False)
    proof_submission_date = Column(Date, nullable=True)
    
    # Total Declared
    total_declared_amount = Column(Numeric(12, 2), default=0)
    total_approved_amount = Column(Numeric(12, 2), default=0)
    
    # Lock
    is_locked = Column(Boolean, default=False)
    locked_at = Column(DateTime, nullable=True)
    
    # Audit
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    __table_args__ = (
        Index('idx_tax_decl_emp_fy', 'employee_id', 'financial_year'),
    )


class TaxDeclarationItem(Base):
    """Individual tax declaration items"""
    __tablename__ = "tax_declaration_items"
    
    id = Column(Integer, primary_key=True, index=True)
    tax_declaration_id = Column(Integer, ForeignKey('tax_declarations.id'), nullable=False, index=True)
    
    # Tax Section
    tax_section = Column(String(20), nullable=False)  # '80C', '80D', 'HRA', etc.
    investment_type = Column(String(100), nullable=False)
    # 'PPF', 'LIC', 'ELSS', 'Home Loan Principal', 'Health Insurance', etc.
    
    # Amount
    declared_amount = Column(Numeric(10, 2), nullable=False)
    approved_amount = Column(Numeric(10, 2), nullable=True)
    
    # Limit
    section_limit = Column(Numeric(10, 2), nullable=True)
    
    # Proof
    proof_url = Column(String(500), nullable=True)
    proof_number = Column(String(100), nullable=True)  # Policy number, receipt number
    
    # Verification
    is_verified = Column(Boolean, default=False)
    verified_by = Column(Integer, ForeignKey('employees.id'), nullable=True)
    verified_at = Column(DateTime, nullable=True)
    verification_notes = Column(Text, nullable=True)
    
    # Rejection
    is_rejected = Column(Boolean, default=False)
    rejection_reason = Column(Text, nullable=True)
    
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class TaxCalculation(Base):
    """Tax calculation for employees"""
    __tablename__ = "tax_calculations"
    
    id = Column(Integer, primary_key=True, index=True)
    uuid = Column(GUID(), default=uuid.uuid4, unique=True, nullable=False, index=True)
    organization_id = Column(Integer, ForeignKey('organization.id'), nullable=False, index=True)
    
    employee_id = Column(Integer, ForeignKey('employees.id'), nullable=False, index=True)
    financial_year = Column(String(20), nullable=False)
    
    # Calculation Type
    calculation_type = Column(String(20), nullable=False)  # 'projected', 'actual', 'final'
    
    # Tax Regime
    tax_regime = Column(Enum(TaxRegime), nullable=False)
    
    # Income
    gross_annual_income = Column(Numeric(15, 2), nullable=False)
    
    # Exemptions
    standard_deduction = Column(Numeric(10, 2), default=0)
    hra_exemption = Column(Numeric(10, 2), default=0)
    lta_exemption = Column(Numeric(10, 2), default=0)
    professional_tax = Column(Numeric(8, 2), default=0)
    
    # Deductions
    total_80c_deductions = Column(Numeric(10, 2), default=0)
    total_80d_deductions = Column(Numeric(10, 2), default=0)
    total_other_deductions = Column(Numeric(10, 2), default=0)
    total_deductions = Column(Numeric(12, 2), default=0)
    
    # Taxable Income
    taxable_income = Column(Numeric(15, 2), nullable=False)
    
    # Tax Calculation
    tax_on_income = Column(Numeric(12, 2), nullable=False)
    surcharge = Column(Numeric(10, 2), default=0)
    cess = Column(Numeric(10, 2), default=0)
    total_tax = Column(Numeric(12, 2), nullable=False)
    
    # Rebate
    rebate_under_87a = Column(Numeric(8, 2), default=0)
    
    # Final Tax
    net_tax_payable = Column(Numeric(12, 2), nullable=False)
    
    # Monthly TDS
    monthly_tds = Column(Numeric(10, 2), nullable=False)
    
    # YTD
    tds_deducted_ytd = Column(Numeric(12, 2), default=0)
    remaining_tds = Column(Numeric(12, 2), nullable=True)
    
    # Calculation Details (JSON breakdown)
    tax_slab_breakdown = Column(JSON, nullable=True)
    deduction_breakdown = Column(JSON, nullable=True)
    
    # Calculation Date
    calculated_at = Column(DateTime, default=datetime.utcnow)
    calculated_by = Column(Integer, ForeignKey('employees.id'), nullable=True)
    
    # Lock
    is_locked = Column(Boolean, default=False)
    
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    __table_args__ = (
        Index('idx_tax_calc_emp_fy', 'employee_id', 'financial_year'),
    )


# ============================================================================
# BANK FILE GENERATION
# ============================================================================

class BankFile(Base):
    """Bank file generation for salary disbursement"""
    __tablename__ = "bank_files"
    
    id = Column(Integer, primary_key=True, index=True)
    uuid = Column(GUID(), default=uuid.uuid4, unique=True, nullable=False, index=True)
    organization_id = Column(Integer, ForeignKey('organization.id'), nullable=False, index=True)
    
    payroll_period_id = Column(Integer, ForeignKey('payroll_periods.id'), nullable=False, index=True)
    
    file_number = Column(String(50), nullable=False, unique=True)
    file_name = Column(String(255), nullable=False)
    
    # Bank Details
    bank_name = Column(String(150), nullable=True)
    file_format = Column(String(50), nullable=False)  # 'NEFT', 'RTGS', 'CSV', 'Excel', 'Custom'
    
    # Summary
    total_records = Column(Integer, nullable=False)
    total_amount = Column(Numeric(15, 2), nullable=False)
    
    # File
    file_url = Column(String(500), nullable=False)
    file_hash = Column(String(64), nullable=True)  # SHA-256 hash for verification
    
    # Processing
    generated_at = Column(DateTime, default=datetime.utcnow)
    generated_by = Column(Integer, ForeignKey('employees.id'), nullable=False)
    
    # Upload to Bank
    is_uploaded = Column(Boolean, default=False)
    uploaded_at = Column(DateTime, nullable=True)
    upload_reference = Column(String(100), nullable=True)
    
    # Status
    status = Column(String(20), default='generated', nullable=False)
    # 'generated', 'uploaded', 'processed', 'failed'
    
    # Confirmation
    bank_confirmation_received = Column(Boolean, default=False)
    bank_confirmation_date = Column(Date, nullable=True)
    bank_utr_numbers = Column(JSON, nullable=True)  # Array of UTR numbers
    
    created_at = Column(DateTime, default=datetime.utcnow)


class BankFileRecord(Base):
    """Individual records in bank file"""
    __tablename__ = "bank_file_records"
    
    id = Column(Integer, primary_key=True, index=True)
    bank_file_id = Column(Integer, ForeignKey('bank_files.id'), nullable=False, index=True)
    payslip_id = Column(Integer, ForeignKey('payslips.id'), nullable=False)
    
    employee_id = Column(Integer, ForeignKey('employees.id'), nullable=False)
    employee_name = Column(String(200), nullable=False)
    
    # Bank Details
    bank_account_number = Column(String(50), nullable=False)
    ifsc_code = Column(String(20), nullable=True)
    bank_name = Column(String(150), nullable=True)
    
    # Amount
    net_salary = Column(Numeric(12, 2), nullable=False)
    
    # Status
    payment_status = Column(String(20), default='pending', nullable=False)
    utr_number = Column(String(50), nullable=True)
    payment_date = Column(Date, nullable=True)
    
    # Error
    error_message = Column(Text, nullable=True)
    
    created_at = Column(DateTime, default=datetime.utcnow)


# ============================================================================
# EMPLOYEE BANK ACCOUNTS
# ============================================================================

class EmployeeBankAccount(Base):
    """Employee bank account details"""
    __tablename__ = "employee_bank_accounts"
    
    id = Column(Integer, primary_key=True, index=True)
    uuid = Column(GUID(), default=uuid.uuid4, unique=True, nullable=False)
    employee_id = Column(Integer, ForeignKey('employees.id'), nullable=False, index=True)
    
    # Bank Details
    bank_name = Column(String(150), nullable=False)
    branch_name = Column(String(150), nullable=True)
    account_number = Column(String(50), nullable=False)
    account_holder_name = Column(String(200), nullable=False)
    account_type = Column(String(20), nullable=True)  # 'savings', 'current'
    
    # Routing Information
    ifsc_code = Column(String(20), nullable=True)  # India
    swift_code = Column(String(20), nullable=True)  # International
    routing_number = Column(String(20), nullable=True)  # US
    sort_code = Column(String(20), nullable=True)  # UK
    iban = Column(String(50), nullable=True)  # Europe
    
    # Verification
    is_verified = Column(Boolean, default=False)
    verified_at = Column(DateTime, nullable=True)
    verified_by = Column(Integer, ForeignKey('employees.id'), nullable=True)
    verification_method = Column(String(50), nullable=True)  # 'penny_drop', 'manual', 'document'
    
    # Primary Account
    is_primary = Column(Boolean, default=False)
    
    # Salary Split (if multiple accounts)
    salary_percentage = Column(Numeric(5, 2), default=100.00)
    salary_fixed_amount = Column(Numeric(12, 2), nullable=True)
    
    is_active = Column(Boolean, default=True)
    
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    employee = relationship("Employee", foreign_keys=[employee_id], backref="bank_accounts")

    @property
    def employee_uuid(self):
        return self.employee.uuid if self.employee else None


# ============================================================================
# PAYROLL RECONCILIATION
# ============================================================================

class PayrollReconciliation(Base):
    """Payroll reconciliation and variance tracking"""
    __tablename__ = "payroll_reconciliations"
    
    id = Column(Integer, primary_key=True, index=True)
    uuid = Column(GUID(), default=uuid.uuid4, unique=True, nullable=False, index=True)
    organization_id = Column(Integer, ForeignKey('organization.id'), nullable=False, index=True)
    
    payroll_period_id = Column(Integer, ForeignKey('payroll_periods.id'), nullable=False, index=True)
    
    reconciliation_number = Column(String(50), nullable=False, unique=True)
    reconciliation_date = Column(Date, nullable=False)
    
    # Comparison
    previous_period_id = Column(Integer, ForeignKey('payroll_periods.id'), nullable=True)
    
    # Totals
    current_period_gross = Column(Numeric(15, 2), nullable=False)
    previous_period_gross = Column(Numeric(15, 2), nullable=True)
    gross_variance = Column(Numeric(15, 2), nullable=True)
    gross_variance_percentage = Column(Numeric(5, 2), nullable=True)
    
    current_period_net = Column(Numeric(15, 2), nullable=False)
    previous_period_net = Column(Numeric(15, 2), nullable=True)
    net_variance = Column(Numeric(15, 2), nullable=True)
    net_variance_percentage = Column(Numeric(5, 2), nullable=True)
    
    # Employee Count
    current_employee_count = Column(Integer, nullable=False)
    previous_employee_count = Column(Integer, nullable=True)
    new_joiners = Column(Integer, default=0)
    exits = Column(Integer, default=0)
    
    # Component-wise Variance
    component_variance_details = Column(JSON, nullable=True)
    
    # Issues Found
    issues_found = Column(Integer, default=0)
    issues_resolved = Column(Integer, default=0)
    issues_pending = Column(Integer, default=0)
    
    # Status
    status = Column(String(20), default='in_progress', nullable=False)
    # 'in_progress', 'completed', 'approved'
    
    # Approval
    reviewed_by = Column(Integer, ForeignKey('employees.id'), nullable=True)
    reviewed_at = Column(DateTime, nullable=True)
    
    # Report
    report_url = Column(String(500), nullable=True)
    
    # Notes
    notes = Column(Text, nullable=True)
    
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    created_by = Column(Integer, ForeignKey('employees.id'), nullable=True)


class PayrollReconciliationIssue(Base):
    """Issues found during reconciliation"""
    __tablename__ = "payroll_reconciliation_issues"
    
    id = Column(Integer, primary_key=True, index=True)
    reconciliation_id = Column(Integer, ForeignKey('payroll_reconciliations.id'), nullable=False, index=True)
    
    employee_id = Column(Integer, ForeignKey('employees.id'), nullable=True)
    payslip_id = Column(Integer, ForeignKey('payslips.id'), nullable=True)
    
    issue_type = Column(String(50), nullable=False)
    # 'missing_component', 'incorrect_calculation', 'duplicate_payment', 
    # 'missing_deduction', 'variance_threshold'
    
    issue_description = Column(Text, nullable=False)
    
    # Impact
    financial_impact = Column(Numeric(12, 2), nullable=True)
    
    # Resolution
    status = Column(String(20), default='open', nullable=False)
    # 'open', 'in_progress', 'resolved', 'closed', 'ignored'
    
    resolution_notes = Column(Text, nullable=True)
    resolved_by = Column(Integer, ForeignKey('employees.id'), nullable=True)
    resolved_at = Column(DateTime, nullable=True)
    
    # Severity
    severity = Column(String(20), default='medium')  # 'low', 'medium', 'high', 'critical'
    
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


# ============================================================================
# PAYROLL JOURNAL ENTRIES (For Accounting Integration)
# ============================================================================

class PayrollJournalEntry(Base):
    """Journal entries for payroll accounting"""
    __tablename__ = "payroll_journal_entries"
    
    id = Column(Integer, primary_key=True, index=True)
    uuid = Column(GUID(), default=uuid.uuid4, unique=True, nullable=False, index=True)
    organization_id = Column(Integer, ForeignKey('organization.id'), nullable=False, index=True)
    
    payroll_period_id = Column(Integer, ForeignKey('payroll_periods.id'), nullable=False, index=True)
    
    entry_number = Column(String(50), nullable=False, unique=True)
    entry_date = Column(Date, nullable=False)
    
    # Accounting Period
    accounting_period = Column(String(20), nullable=False)  # "Jan-2024"
    financial_year = Column(String(20), nullable=False)
    
    # Entry Type
    entry_type = Column(String(50), nullable=False)
    # 'salary_expense', 'deductions', 'employer_contributions', 'provisions'
    
    # Total
    total_debit = Column(Numeric(15, 2), nullable=False)
    total_credit = Column(Numeric(15, 2), nullable=False)
    
    # Status
    status = Column(String(20), default='draft', nullable=False)
    # 'draft', 'posted', 'reversed'
    
    # Export to ERP
    is_exported = Column(Boolean, default=False)
    exported_at = Column(DateTime, nullable=True)
    export_reference = Column(String(100), nullable=True)
    erp_journal_id = Column(String(100), nullable=True)
    
    # Reversal
    is_reversed = Column(Boolean, default=False)
    reversed_at = Column(DateTime, nullable=True)
    reversal_entry_id = Column(Integer, ForeignKey('payroll_journal_entries.id'), nullable=True)
    
    # Narration
    narration = Column(Text, nullable=True)
    
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    created_by = Column(Integer, ForeignKey('employees.id'), nullable=True)


class PayrollJournalEntryLine(Base):
    """Journal entry line items"""
    __tablename__ = "payroll_journal_entry_lines"
    
    id = Column(Integer, primary_key=True, index=True)
    journal_entry_id = Column(Integer, ForeignKey('payroll_journal_entries.id'), nullable=False, index=True)
    
    line_number = Column(Integer, nullable=False)
    
    # Account
    account_code = Column(String(50), nullable=False)
    account_name = Column(String(200), nullable=False)
    account_type = Column(String(20), nullable=False)  # 'expense', 'liability', 'asset'
    
    # Cost Center
    cost_center_id = Column(Integer, ForeignKey('cost_centers.id'), nullable=True)
    department_id = Column(Integer, ForeignKey('departments.id'), nullable=True)
    location_id = Column(Integer, ForeignKey('locations.id'), nullable=True)
    
    # Amount
    debit_amount = Column(Numeric(12, 2), default=0)
    credit_amount = Column(Numeric(12, 2), default=0)
    
    # Description
    description = Column(Text, nullable=True)
    
    # Reference
    component_id = Column(Integer, ForeignKey('salary_components.id'), nullable=True)
    
    created_at = Column(DateTime, default=datetime.utcnow)


# ============================================================================
# STATUTORY FORMS & COMPLIANCE
# ============================================================================

class StatutoryForm(Base):
    """Statutory forms and compliance documents"""
    __tablename__ = "statutory_forms"
    
    id = Column(Integer, primary_key=True, index=True)
    uuid = Column(GUID(), default=uuid.uuid4, unique=True, nullable=False, index=True)
    organization_id = Column(Integer, ForeignKey('organization.id'), nullable=False, index=True)
    
    form_type = Column(String(50), nullable=False)
    # 'form_16', 'form_24q', 'pf_challan', 'esi_challan', 'professional_tax', etc.
    
    form_name = Column(String(150), nullable=False)
    form_number = Column(String(50), nullable=False, unique=True)
    
    # Period
    financial_year = Column(String(20), nullable=False)
    period = Column(String(50), nullable=True)  # "Q1", "January", etc.
    period_start_date = Column(Date, nullable=True)
    period_end_date = Column(Date, nullable=True)
    
    # Filing
    filing_deadline = Column(Date, nullable=True)
    filing_status = Column(String(20), default='pending', nullable=False)
    # 'pending', 'filed', 'accepted', 'rejected', 'revised'
    
    filed_at = Column(DateTime, nullable=True)
    filed_by = Column(Integer, ForeignKey('employees.id'), nullable=True)
    filing_reference = Column(String(100), nullable=True)
    acknowledgment_number = Column(String(100), nullable=True)
    
    # Document
    form_url = Column(String(500), nullable=True)
    acknowledgment_url = Column(String(500), nullable=True)
    
    # Amount (if applicable)
    amount = Column(Numeric(15, 2), nullable=True)
    
    # Notes
    notes = Column(Text, nullable=True)
    
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    created_by = Column(Integer, ForeignKey('employees.id'), nullable=True)


# ============================================================================
# PAYROLL AUDIT LOG
# ============================================================================

class PayrollAuditLog(Base):
    """Comprehensive audit trail for payroll"""
    __tablename__ = "payroll_audit_logs"
    
    id = Column(Integer, primary_key=True, index=True)
    uuid = Column(GUID(), default=uuid.uuid4, unique=True, nullable=False)
    organization_id = Column(Integer, ForeignKey('organization.id'), nullable=False, index=True)
    
    # Action Details
    action_type = Column(String(50), nullable=False, index=True)
    # 'salary_created', 'salary_updated', 'payroll_processed', 'payslip_generated',
    # 'payment_approved', 'component_modified', 'loan_approved', etc.
    
    entity_type = Column(String(50), nullable=False)  # 'payroll_period', 'payslip', 'salary', 'loan'
    entity_id = Column(Integer, nullable=False, index=True)
    
    # Employee Reference
    employee_id = Column(Integer, ForeignKey('employees.id'), nullable=True, index=True)
    
    # Before/After State
    before_state = Column(JSON, nullable=True)
    after_state = Column(JSON, nullable=True)
    
    # Changes
    changed_fields = Column(JSON, nullable=True)
    change_summary = Column(Text, nullable=True)
    
    # User & Context
    performed_by = Column(Integer, ForeignKey('employees.id'), nullable=True, index=True)
    ip_address = Column(String(50), nullable=True)
    user_agent = Column(Text, nullable=True)
    
    # Risk Level
    risk_level = Column(String(20), nullable=True)  # 'low', 'medium', 'high', 'critical'
    
    # Timestamp
    performed_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    
    __table_args__ = (
        Index('idx_payroll_audit_entity', 'entity_type', 'entity_id'),
        Index('idx_payroll_audit_action', 'action_type', 'performed_at'),
    )


# ============================================================================
# INDEXES FOR PERFORMANCE
# ============================================================================

# Additional composite indexes for complex queries
Index('idx_payslip_emp_fy', Payslip.employee_id, Payslip.period_start_date, Payslip.period_end_date)
Index('idx_payroll_period_fy_status', PayrollPeriod.financial_year, PayrollPeriod.status)
Index('idx_tax_decl_emp_status', TaxDeclaration.employee_id, TaxDeclaration.status, TaxDeclaration.financial_year)
