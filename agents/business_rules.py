"""
business_rules.py — Payroll-specific business rules and constants for the Agent.
These are injected into the Generator agent prompt so it produces correct logic.
"""

PERMISSION_CODES = {
    # PAYROLL MODULE — codes 101 onwards
    "salary_components": {"READ": "101", "CREATE": "102", "UPDATE": "103", "DELETE": "104"},
    "salary_templates":  {"READ": "101", "CREATE": "102", "UPDATE": "103", "DELETE": "104"},
    "employee_salaries": {"READ": "105", "CREATE": "106", "UPDATE": "107", "DELETE": "108"},
    "payroll_periods":   {"READ": "109", "CREATE": "110", "UPDATE": "111", "PROCESS": "112"},
    "payslips":          {"READ": "113", "PUBLISH": "114", "REVERSE": "115"},
    "loans":             {"READ": "116", "CREATE": "117", "APPROVE": "118"},
    "reimbursements":    {"READ": "119", "CREATE": "120", "APPROVE": "121"},
    "tax_declarations":  {"READ": "122", "CREATE": "123", "APPROVE": "124"},
    "bank_files":        {"READ": "125", "CREATE": "126"},
    "audit_logs":        {"READ": "127"},
    "final_settlements": {"READ": "128", "CREATE": "129", "APPROVE": "130"},
    "arrears":           {"READ": "131", "CREATE": "132", "APPROVE": "133"},
    "reports":           {"READ": "134"},
    "statutory_forms":   {"READ": "135", "CREATE": "136"},
    "reconciliations":   {"READ": "137", "CREATE": "138"},
    "journal_entries":   {"READ": "139", "CREATE": "140"},
}

# Module priority order (matches API list)
MODULE_PRIORITY = [
    "salary_components",
    "salary_templates",
    "employee_salaries",
    "payroll_periods",
    "payslips",
    "loans",
    "reimbursements",
    "final_settlements",
    "arrears_one_time",
    "tax_declarations",
    "bank_files",
    "reconciliations",
    "journal_entries",
    "statutory_forms",
    "reports",
    "bulk_operations",
    "bank_accounts",
    "audit_logs",
]

# Business rules injected per module
MODULE_RULES = {
    "salary_components": """
BUSINESS RULES:
- component_code must be unique per organization (composite index: organization_id + component_code)
- Cannot DELETE (hard delete) a salary component; use soft-deactivation (is_active=False)
- Cannot deactivate if the component is used in any ACTIVE salary template
- Validate that calculation_value is provided when calculation_type is FIXED or PERCENTAGE
- Validate that calculation_formula is provided when calculation_type is FORMULA
- component_type must be one of: EARNING, DEDUCTION, EMPLOYER_CONTRIBUTION
- GET list: filter by organization_id, component_type (optional), is_active (optional), search (name/code)
- GET list: paginated response with total_records, current_page, total_pages, page_size
- GET detail: use UUID in URL path (not integer id)
- PUT update: do NOT allow changing component_code if the component is used in templates
- Lookup endpoint (no pagination, used in dropdowns)
""",

    "salary_templates": """
BUSINESS RULES:
- template_code must be unique per organization
- Cannot delete a template that is currently assigned to any active employee salary
- effective_from must be before effective_to (if effective_to is provided)
- Only one default template per organization (is_default=True); when setting a new default, unset the previous one
- CLONE endpoint: create a new template with all its components, using a new name provided in the request body
- PREVIEW endpoint: given annual_ctc as query param, compute monthly amounts for each component 
  based on calculation_type (FIXED uses calculation_value_override, PERCENTAGE uses percentage of basic etc.)
- COMPONENTS endpoint: accepts array of {component_uuid, calculation_type_override, calculation_value_override, display_order}
  Creates or replaces the template components (full replace semantics like roles/permissions)
""",

    "employee_salaries": """
BUSINESS RULES:
- Only ONE active salary per employee (is_active=True + no effective_to)
- SALARY REVISION: when creating a revision, the old active salary's effective_to is set to (new effective_from - 1 day)
  and is_active is set to False. The new salary record's previous_salary_id links to the old one.
- HOLD: set is_on_hold=True, hold_reason, hold_from_date. Validation: cannot already be on hold.
- RELEASE HOLD: set is_on_hold=False, clear hold_reason and hold_from_date.
- CTC BREAKDOWN: compute annual and monthly amounts for each salary component using calculation rules.
  For PERCENTAGE type: value = (calculation_value / 100) * basic_salary
  For FIXED type: value = calculation_value
- GET list: filter by employee_id (UUID), department_id, is_active, effective_from, page, limit
- SELF-ACCESS: employees can view their own salary. HR/Payroll can view all.
""",

    "payroll_periods": """
BUSINESS RULES:
- period_code must be unique per organization
- No overlapping periods for the same organization and pay_frequency
- PROCESS endpoint: 
  * Checks period is in DRAFT or IN_PROGRESS status
  * Option: should_proceed_background (bool, default False)
  * If background: use FastAPI BackgroundTasks, return 202 Accepted with processing_started status
  * If synchronous: compute payslips for all active employees, return summary
  * Status transitions: DRAFT → IN_PROGRESS → PROCESSED
- SUBMIT FOR APPROVAL: PROCESSED → PENDING_APPROVAL
- APPROVE: PENDING_APPROVAL → APPROVED. Record approved_by, approved_at, approval_comments.
- PUBLISH: APPROVED → PUBLISHED. Marks all payslips is_published=True. Records published_at, published_by.
- LOCK: Set is_locked=True. Cannot edit locked period. Record locked_by, locked_at.
- UNLOCK: Requires unlock_reason. Set is_locked=False.
- REVERSE: Only PROCESSED/APPROVED periods. Status → REVERSED. Reverse all payslips.
- HOLD: Set status=ON_HOLD, record hold_reason.
- SUMMARY endpoint: returns total_employees, total_gross_amount, total_deductions, total_net_amount,
  total_employer_contributions, breakdown by department.
""",

    "payslips": """
BUSINESS RULES:
- GET list: filter by period_id, employee_id, department_id, status, from_date, to_date, page, limit
- SELF-ACCESS: employees can only see their own payslips
- DOWNLOAD: serve payslip PDF from payslip_pdf_url. If not generated, return 404 with message.
- REGENERATE: re-compute payslip for the employee. Period must not be in PAID status.
- SEND EMAIL: send payslip PDF to employee's email. Record email_sent=True, email_sent_at.
- BULK EMAIL: accepts array of payslip UUIDs. Sends email to each. Returns bulk summary.
- HOLD: set is_on_hold=True, hold_reason. Cannot hold a published payslip.
- REVERSE: create a reversal entry. Set is_reversed=True, reversed_at, reversed_by, reversal_reason.
  Links reversed_payslip_id to self.
- EXPORT: returns file download. Query params: period_id, format (csv/excel). 
""",

    "loans": """
BUSINESS RULES:
- loan_number is auto-generated: "LN-{employee_code}-{YYYYMMDDHHMMSS}"
- Status machine: PENDING → APPROVED → ACTIVE (on disburse) → COMPLETED (all installments paid) | REJECTED | WRITTEN_OFF
- APPROVE: set status=APPROVED, approved_by, approved_at, approval_comments
- REJECT: set status=REJECTED, rejection_reason, rejected_at
- DISBURSE: set status=ACTIVE, disbursement_date, disbursement_mode, disbursement_reference
  Auto-generate LoanRepayment schedule: create N installment records with due_date calculated from repayment_start_date
  Monthly installment = total_payable / number_of_installments
- REPAYMENT SCHEDULE: return all LoanRepayment rows for the loan, sorted by due_date
- PENDING REPAYMENTS: return all LoanRepayment where is_paid=False and due_date <= today, org-wide
- Cannot approve a loan that is not in PENDING status
- Cannot disburse a loan that is not in APPROVED status
- SELF-ACCESS: employees can view and apply for their own loans
""",

    "reimbursements": """
BUSINESS RULES:
- claim_number is auto-generated: "RC-{employee_code}-{YYYYMMDDHHMMSS}"
- Status machine: DRAFT → SUBMITTED → APPROVED → PAID | REJECTED
- SUBMIT: DRAFT → SUBMITTED. Sets approver based on employee's reporting_manager_id
- APPROVE: SUBMITTED → APPROVED. Record approved_by, approved_at. Can adjust approved_amount.
- REJECT: SUBMITTED → REJECTED. Record rejection_reason, rejected_at.
- Cannot update a claim that is not in DRAFT status
- Category limits: validate claim_amount <= category.max_claim_per_transaction (if set)
- PENDING APPROVALS: return claims where status=SUBMITTED and approver_id = current_user.id
- GET /employees/{employee_id}/reimbursements: return that employee's claims, filter by status, financial_year
- SELF-ACCESS: employees can view/create/submit their own claims
""",

    "tax_declarations": """
BUSINESS RULES:
- One tax declaration per employee per financial_year
- Status machine: DRAFT → SUBMITTED → APPROVED | REJECTED
- SUBMIT: DRAFT → SUBMITTED. Validates all items are within section limits.
- APPROVE: item-by-item approval. Sets approved_amount per item (may be <= declared_amount).
- LOCK: Set is_locked=True. Cannot add/edit items after locking.
- Cannot submit a locked declaration.
- Section limits (common Indian sections for reference, but keep generic):
  section_limit is stored on TaxDeclarationItem itself
- TAX CALCULATION endpoint: 
  * Reads employee's active salary, tax declarations, and financial year
  * Computes: gross_annual_income, standard_deduction, exemptions, taxable_income, tax slabs
  * Tax regime: OLD (with deductions) vs NEW (flat slabs without deductions)
  * Returns breakdown as JSON
- BULK TAX CALCULATION: process all employees for the org, store results in TaxCalculation table
- TAX REGIME COMPARISON: compute tax under both OLD and NEW regime, return comparison
""",

    "bank_files": """
BUSINESS RULES:
- GENERATE: accepts period_id (UUID). Period must be in APPROVED or PROCESSED status.
  Creates BankFile record and N BankFileRecord rows (one per payslip/employee).
  file_number auto-generated: "BF-{period_code}-{timestamp}"
  Returns file metadata (not the actual file yet)
- DOWNLOAD: returns the bank file. Format: NEFT/RTGS/CSV based on query param.
  If file_url exists, stream it. Otherwise generate on-the-fly.
- UPLOAD CONFIRMATION: accepts UTR numbers per employee.
  Sets bank_confirmation_received=True, bank_confirmation_date, bank_utr_numbers.
- GET RECORDS: returns BankFileRecord rows for a file, filter by payment_status.
""",

    "final_settlements": """
BUSINESS RULES:
- One settlement per employee (unique on employee_id)
- CALCULATE endpoint: auto-computes all settlement components:
  * Leave encashment: leave_balance_days * per_day_salary
  * Gratuity: if tenure >= 5 years: (basic * 15 / 26) * years_of_service
  * Notice pay recovery: (daily_salary * notice_period_shortage) if notice not served
  * Net = total_earnings - total_recoveries - tax_deducted
- APPROVE: PENDING → APPROVED. Set approved_by, approved_at.
- PROCESS PAYMENT: APPROVED → PAID. Set paid_at, payment_mode, payment_reference.
- settlement_number auto-generated: "FS-{employee_code}-{YYYY}"
""",

    "arrears_one_time": """
BUSINESS RULES:
- arrear_number auto-generated: "AR-{employee_code}-{YYYYMM}"
- Status machine: PENDING → APPROVED → PAID
- APPROVE arrear/one-time payment: set status=APPROVED, approved_by, approved_at
- One-time payment: same pattern as arrear (separate endpoint prefix: /one-time-payments)
- payment_number auto-generated for one-time: "OTP-{employee_code}-{timestamp}"
""",

    "audit_logs": """
BUSINESS RULES:
- READ ONLY: no create/update/delete via API. Logs are written internally by other endpoints.
- Filter by: action_type, entity_type, employee_id (UUID), performed_by (UUID), from_date, to_date, page, limit
- EXPORT: returns CSV/Excel file. Filter params same as GET list.
- COMPLIANCE CHECK: scans for common violations (e.g., payroll processed without approval, 
  salary changed without revision record). Returns list of violations.
""",

    "reports": """
BUSINESS RULES:
- All report endpoints are READ-ONLY GET endpoints
- Common filter params: period_id (UUID), financial_year, department_id (UUID), location_id (UUID)
- SALARY REGISTER: one row per employee per period. Columns: employee details + all component amounts.
- VARIANCE: compare current period vs previous period, show % change per component.
- YTD EARNINGS: sum of each component from April 1 to today for each employee.
- COST CENTER ALLOCATION: join payslip components with employee cost center assignment.
- All report responses: {success: bool, message: str, data: [...], pagination: {...}}
""",

    "reconciliations": """
BUSINESS RULES:
- One reconciliation per payroll period
- CREATE: compares current_period_gross vs previous_period_gross. Computes variance. 
  Flags issues if variance > 10% for any component.
- ISSUES: returned as PayrollReconciliationIssue rows. Severity: CRITICAL / MAJOR / MINOR
- RESOLVE ISSUE: set issue.is_resolved=True, resolution_notes.
- APPROVE: all CRITICAL issues must be resolved before approval.
- EXPORT: returns PDF/Excel report.
""",

    "journal_entries": """
BUSINESS RULES:
- GENERATE: accepts period_id. Creates journal entry with debit/credit lines.
  Debits: salary expense accounts per department/cost center
  Credits: liability accounts (net pay, PF payable, ESI payable, TDS payable)
- POST: entry_status → POSTED. Cannot edit after posting.
- EXPORT TO ERP: marks is_exported=True, exported_at, export_reference. Returns ERP ref number.
- REVERSE: creates a new journal entry that negates all lines of the original.
""",

    "statutory_forms": """
BUSINESS RULES:
- GENERATE: accepts form_type (PF_ECR, ESI_RETURN, PT_RETURN, TDS_24Q, TDS_26Q, FORM_16)
  Creates StatutoryForm record with computed data.
- DOWNLOAD: returns PDF/Excel based on form_type.
- FILE: mark as filed. Set filing_status=FILED, filed_at, filing_reference, acknowledgment_number.
- FORM 16: requires financial_year query param. Individual form per employee.
- BULK FORM 16: generate for all employees. Returns job ID (async) or summary (sync).
""",
}

# Routing map (prefix → endpoint file suffix)  
ROUTE_MAP = {
    "salary_components":    "/payroll/salary-components",
    "salary_templates":     "/payroll/salary-templates",
    "employee_salaries":    "/payroll/employee-salaries",
    "payroll_periods":      "/payroll/periods",
    "payslips":             "/payroll/payslips",
    "loans":                "/payroll/loans",
    "reimbursements":       "/payroll/reimbursements",
    "final_settlements":    "/payroll/final-settlements",
    "arrears_one_time":     "/payroll/arrears",
    "tax_declarations":     "/payroll/tax-declarations",
    "bank_files":           "/payroll/bank-files",
    "reconciliations":      "/payroll/reconciliations",
    "journal_entries":      "/payroll/journal-entries",
    "statutory_forms":      "/payroll/statutory-forms",
    "reports":              "/payroll/reports",
    "bulk_operations":      "/payroll/bulk",
    "bank_accounts":        "/payroll/bank-accounts",
    "audit_logs":           "/payroll/audit-log",
}
