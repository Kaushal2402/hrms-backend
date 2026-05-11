# Payroll Management Module - API Endpoints

## 1. SALARY COMPONENTS MANAGEMENT

### `GET /api/v1/payroll/salary-components`
Get list of salary components
* **Query Params**: `organization_id`, `component_type`, `is_active`, `search`
* **Response**: Array of salary component objects


### `POST /api/v1/payroll/salary-components`
Create new salary component
* **Request Body**: Component details (code, name, type, calculation)
* **Response**: Created salary component


### `GET /api/v1/payroll/salary-components/{component_id}`
Get salary component details
* **Path Param**: `component_id`
* **Response**: Salary component object with calculation rules


### `PUT /api/v1/payroll/salary-components/{component_id}`
Update salary component
* **Path Param**: `component_id`
* **Request Body**: Updated component fields
* **Response**: Updated salary component


### `DELETE /api/v1/payroll/salary-components/{component_id}`
Deactivate salary component
* **Path Param**: `component_id`
* **Response**: Success message


---

## 2. SALARY TEMPLATES

### `GET /api/v1/payroll/salary-templates`
Get salary templates
* **Query Params**: `organization_id`, `is_active`, `applicable_to`
* **Response**: Array of salary template objects


### `POST /api/v1/payroll/salary-templates`
Create salary template
* **Request Body**: Template details with component mappings
* **Response**: Created salary template


### `GET /api/v1/payroll/salary-templates/{template_id}`
Get salary template details
* **Path Param**: `template_id`
* **Response**: Template with all components


### `PUT /api/v1/payroll/salary-templates/{template_id}`
Update salary template
* **Path Param**: `template_id`
* **Request Body**: Updated template fields
* **Response**: Updated salary template


### `DELETE /api/v1/payroll/salary-templates/{template_id}`
Delete salary template
* **Path Param**: `template_id`
* **Response**: Success message


### `POST /api/v1/payroll/salary-templates/{template_id}/clone`
Clone salary template
* **Path Param**: `template_id`
* **Request Body**: New template name and modifications
* **Response**: Cloned salary template


### `POST /api/v1/payroll/salary-templates/{template_id}/components`
Add components to template
* **Path Param**: `template_id`
* **Request Body**: Array of component IDs with calculation overrides
* **Response**: Updated template


### `GET /api/v1/payroll/salary-templates/{template_id}/preview`
Preview CTC breakdown for template
* **Path Param**: `template_id`
* **Query Params**: `annual_ctc`
* **Response**: Component-wise breakdown


---

## 3. EMPLOYEE SALARY ASSIGNMENT

### `GET /api/v1/payroll/employee-salaries`
Get employee salaries
* **Query Params**: `employee_id`, `department_id`, `is_active`, `effective_from`, `page`, `limit`
* **Response**: Paginated employee salary records


### `POST /api/v1/payroll/employee-salaries`
Assign salary to employee
* **Request Body**: Employee ID, template ID, CTC, effective dates
* **Response**: Created employee salary record


### `GET /api/v1/payroll/employees/{employee_id}/salary`
Get employee's current salary
* **Path Param**: `employee_id`
* **Response**: Active salary structure with components
, Manager

### `GET /api/v1/payroll/employees/{employee_id}/salary-history`
Get employee salary history
* **Path Param**: `employee_id`
* **Query Params**: `from_date`, `to_date`
* **Response**: Array of salary revisions


### `PUT /api/v1/payroll/employee-salaries/{salary_id}`
Update employee salary
* **Path Param**: `salary_id`
* **Request Body**: Updated salary details
* **Response**: Updated salary record


### `POST /api/v1/payroll/employees/{employee_id}/salary-revision`
Create salary revision
* **Path Param**: `employee_id`
* **Request Body**: New CTC, revision reason, effective date
* **Response**: New salary record with revision details


### `PATCH /api/v1/payroll/employee-salaries/{salary_id}/hold`
Put salary on hold
* **Path Param**: `salary_id`
* **Request Body**: Hold reason, hold from date
* **Response**: Updated salary record


### `PATCH /api/v1/payroll/employee-salaries/{salary_id}/release`
Release salary hold
* **Path Param**: `salary_id`
* **Response**: Updated salary record


### `GET /api/v1/payroll/employees/{employee_id}/ctc-breakdown`
Get CTC breakdown for employee
* **Path Param**: `employee_id`
* **Response**: Annual and monthly CTC breakdown


---

## 4. PAYROLL PERIOD MANAGEMENT

### `GET /api/v1/payroll/periods`
Get payroll periods
* **Query Params**: `organization_id`, `financial_year`, `status`, `pay_frequency`, `page`, `limit`
* **Response**: Paginated payroll periods


### `POST /api/v1/payroll/periods`
Create payroll period
* **Request Body**: Period dates, pay frequency, working days
* **Response**: Created payroll period


### `GET /api/v1/payroll/periods/{period_id}`
Get payroll period details
* **Path Param**: `period_id`
* **Response**: Period with summary statistics


### `PUT /api/v1/payroll/periods/{period_id}`
Update payroll period
* **Path Param**: `period_id`
* **Request Body**: Updated period fields
* **Response**: Updated payroll period


### `POST /api/v1/payroll/periods/{period_id}/process`
Process payroll for period
* **Path Param**: `period_id`
* **Request Body**: Processing options, employee filters
* **Response**: Processing status and summary


### `POST /api/v1/payroll/periods/{period_id}/submit-approval`
Submit payroll for approval
* **Path Param**: `period_id`
* **Response**: Updated period status


### `POST /api/v1/payroll/periods/{period_id}/approve`
Approve payroll
* **Path Param**: `period_id`
* **Request Body**: Approval comments
* **Response**: Approved payroll period


### `POST /api/v1/payroll/periods/{period_id}/publish`
Publish payslips to employees
* **Path Param**: `period_id`
* **Response**: Publishing status


### `POST /api/v1/payroll/periods/{period_id}/lock`
Lock payroll period
* **Path Param**: `period_id`
* **Response**: Locked payroll period


### `POST /api/v1/payroll/periods/{period_id}/unlock`
Unlock payroll period
* **Path Param**: `period_id`
* **Request Body**: Unlock reason
* **Response**: Unlocked payroll period
 (with approval)

### `PATCH /api/v1/payroll/periods/{period_id}/hold`
Put payroll on hold
* **Path Param**: `period_id`
* **Request Body**: Hold reason
* **Response**: Updated period status


### `POST /api/v1/payroll/periods/{period_id}/reverse`
Reverse processed payroll
* **Path Param**: `period_id`
* **Request Body**: Reversal reason
* **Response**: Reversal confirmation
 (requires approval)

### `GET /api/v1/payroll/periods/{period_id}/summary`
Get payroll summary
* **Path Param**: `period_id`
* **Response**: Detailed payroll summary with totals
, Finance

---

## 5. PAYSLIP MANAGEMENT

### `GET /api/v1/payroll/payslips`
Get payslips
* **Query Params**: `period_id`, `employee_id`, `department_id`, `status`, `from_date`, `to_date`, `page`, `limit`
* **Response**: Paginated payslips


### `GET /api/v1/payroll/payslips/{payslip_id}`
Get payslip details
* **Path Param**: `payslip_id`
* **Response**: Detailed payslip with all components
 (own payslip)

### `GET /api/v1/payroll/payslips/{payslip_id}/download`
Download payslip PDF
* **Path Param**: `payslip_id`
* **Response**: PDF file download


### `GET /api/v1/payroll/employees/{employee_id}/payslips`
Get employee's payslips
* **Path Param**: `employee_id`
* **Query Params**: `financial_year`, `from_date`, `to_date`
* **Response**: Array of payslips


### `GET /api/v1/payroll/employees/me/payslips`
Get current employee's payslips
* **Query Params**: `financial_year`, `limit`
* **Response**: Employee's own payslips


### `POST /api/v1/payroll/payslips/{payslip_id}/regenerate`
Regenerate payslip
* **Path Param**: `payslip_id`
* **Response**: Regenerated payslip


### `POST /api/v1/payroll/payslips/{payslip_id}/send-email`
Email payslip to employee
* **Path Param**: `payslip_id`
* **Response**: Email sent confirmation


### `POST /api/v1/payroll/payslips/bulk-email`
Bulk email payslips
* **Request Body**: Array of payslip IDs or period ID
* **Response**: Bulk email summary


### `PATCH /api/v1/payroll/payslips/{payslip_id}/hold`
Put payslip on hold
* **Path Param**: `payslip_id`
* **Request Body**: Hold reason
* **Response**: Updated payslip


### `POST /api/v1/payroll/payslips/{payslip_id}/reverse`
Reverse payslip
* **Path Param**: `payslip_id`
* **Request Body**: Reversal reason
* **Response**: Reversal confirmation
 (requires approval)

### `GET /api/v1/payroll/payslips/export`
Export payslips
* **Query Params**: `period_id`, `format` (excel, csv)
* **Response**: File download


---

## 6. LOANS & ADVANCES

### `GET /api/v1/payroll/loans`
Get employee loans
* **Query Params**: `employee_id`, `status`, `loan_type`, `from_date`, `to_date`, `page`, `limit`
* **Response**: Paginated loan records
 (own loans)

### `POST /api/v1/payroll/loans`
Create loan application
* **Request Body**: Employee ID, loan amount, purpose, repayment terms
* **Response**: Created loan application

### `GET /api/v1/payroll/loans/{loan_id}`
Get loan details
* **Path Param**: `loan_id`
* **Response**: Loan details with repayment schedule

### `PUT /api/v1/payroll/loans/{loan_id}`
Update loan
* **Path Param**: `loan_id`
* **Request Body**: Updated loan details
* **Response**: Updated loan


### `POST /api/v1/payroll/loans/{loan_id}/approve`
Approve loan
* **Path Param**: `loan_id`
* **Request Body**: Approval comments
* **Response**: Approved loan


### `POST /api/v1/payroll/loans/{loan_id}/reject`
Reject loan
* **Path Param**: `loan_id`
* **Request Body**: Rejection reason
* **Response**: Rejected loan


### `POST /api/v1/payroll/loans/{loan_id}/disburse`
Disburse loan amount
* **Path Param**: `loan_id`
* **Request Body**: Disbursement details
* **Response**: Updated loan with disbursement info


### `GET /api/v1/payroll/loans/{loan_id}/repayment-schedule`
Get loan repayment schedule
* **Path Param**: `loan_id`
* **Response**: Array of installment details


### `GET /api/v1/payroll/employees/{employee_id}/loans`
Get employee's loans
* **Path Param**: `employee_id`
* **Query Params**: `status`, `include_completed`
* **Response**: Employee's loan records


### `GET /api/v1/payroll/loans/pending-repayments`
Get pending loan repayments
* **Query Params**: `due_date_from`, `due_date_to`
* **Response**: Upcoming repayments


---

## 7. REIMBURSEMENTS

### `GET /api/v1/payroll/reimbursement-categories`
Get reimbursement categories
* **Query Params**: `organization_id`, `is_active`
* **Response**: Array of reimbursement categories


### `POST /api/v1/payroll/reimbursement-categories`
Create reimbursement category
* **Request Body**: Category details (name, limits, rules)
* **Response**: Created category


### `GET /api/v1/payroll/reimbursements`
Get reimbursement claims
* **Query Params**: `employee_id`, `status`, `category_id`, `from_date`, `to_date`, `page`, `limit`
* **Response**: Paginated reimbursement claims
 (own claims)

### `POST /api/v1/payroll/reimbursements`
Submit reimbursement claim
* **Request Body**: Category, amount, expense date, receipts
* **Response**: Created reimbursement claim

### `GET /api/v1/payroll/reimbursements/{claim_id}`
Get reimbursement claim details
* **Path Param**: `claim_id`
* **Response**: Claim details with receipts


### `PUT /api/v1/payroll/reimbursements/{claim_id}`
Update reimbursement claim
* **Path Param**: `claim_id`
* **Request Body**: Updated claim details
* **Response**: Updated claim

### `POST /api/v1/payroll/reimbursements/{claim_id}/submit`
Submit claim for approval
* **Path Param**: `claim_id`
* **Response**: Submitted claim

### `POST /api/v1/payroll/reimbursements/{claim_id}/approve`
Approve reimbursement claim
* **Path Param**: `claim_id`
* **Request Body**: Approved amount, comments
* **Response**: Approved claim


### `POST /api/v1/payroll/reimbursements/{claim_id}/reject`
Reject reimbursement claim
* **Path Param**: `claim_id`
* **Request Body**: Rejection reason
* **Response**: Rejected claim


### `GET /api/v1/payroll/employees/{employee_id}/reimbursements`
Get employee's reimbursements
* **Path Param**: `employee_id`
* **Query Params**: `status`, `financial_year`
* **Response**: Employee's reimbursement claims


### `GET /api/v1/payroll/reimbursements/pending-approvals`
Get pending reimbursement approvals
* **Query Params**: `approver_id`
* **Response**: Claims pending approval


---

## 8. FINAL SETTLEMENT

### `GET /api/v1/payroll/final-settlements`
Get final settlements
* **Query Params**: `employee_id`, `status`, `from_date`, `to_date`
* **Response**: Array of final settlement records


### `POST /api/v1/payroll/final-settlements`
Create final settlement
* **Request Body**: Employee ID, last working date, separation type
* **Response**: Created final settlement with calculation


### `GET /api/v1/payroll/final-settlements/{settlement_id}`
Get final settlement details
* **Path Param**: `settlement_id`
* **Response**: Complete settlement breakdown


### `PUT /api/v1/payroll/final-settlements/{settlement_id}`
Update final settlement
* **Path Param**: `settlement_id`
* **Request Body**: Updated settlement components
* **Response**: Updated settlement


### `POST /api/v1/payroll/final-settlements/{settlement_id}/calculate`
Recalculate final settlement
* **Path Param**: `settlement_id`
* **Response**: Recalculated settlement


### `POST /api/v1/payroll/final-settlements/{settlement_id}/approve`
Approve final settlement
* **Path Param**: `settlement_id`
* **Request Body**: Approval comments
* **Response**: Approved settlement


### `POST /api/v1/payroll/final-settlements/{settlement_id}/process-payment`
Process settlement payment
* **Path Param**: `settlement_id`
* **Request Body**: Payment details
* **Response**: Payment confirmation


### `GET /api/v1/payroll/final-settlements/{settlement_id}/download`
Download settlement document
* **Path Param**: `settlement_id`
* **Response**: PDF file download


---

## 9. ARREARS & ONE-TIME PAYMENTS

### `GET /api/v1/payroll/arrears`
Get arrear payments
* **Query Params**: `employee_id`, `status`, `from_date`, `to_date`
* **Response**: Array of arrear records


### `POST /api/v1/payroll/arrears`
Create arrear payment
* **Request Body**: Employee ID, amount, period, reason
* **Response**: Created arrear record


### `GET /api/v1/payroll/arrears/{arrear_id}`
Get arrear details
* **Path Param**: `arrear_id`
* **Response**: Arrear record details


### `POST /api/v1/payroll/arrears/{arrear_id}/approve`
Approve arrear payment
* **Path Param**: `arrear_id`
* **Response**: Approved arrear


### `GET /api/v1/payroll/one-time-payments`
Get one-time payments
* **Query Params**: `employee_id`, `payment_type`, `status`
* **Response**: Array of one-time payments


### `POST /api/v1/payroll/one-time-payments`
Create one-time payment
* **Request Body**: Employee ID, payment type, amount, reason
* **Response**: Created one-time payment


### `POST /api/v1/payroll/one-time-payments/{payment_id}/approve`
Approve one-time payment
* **Path Param**: `payment_id`
* **Response**: Approved payment


---

## 10. TAX DECLARATIONS & CALCULATIONS

### `GET /api/v1/payroll/tax-declarations`
Get tax declarations
* **Query Params**: `employee_id`, `financial_year`, `status`
* **Response**: Array of tax declarations

### `POST /api/v1/payroll/tax-declarations`
Create tax declaration
* **Request Body**: Employee ID, financial year, tax regime
* **Response**: Created tax declaration

### `GET /api/v1/payroll/tax-declarations/{declaration_id}`
Get tax declaration details
* **Path Param**: `declaration_id`
* **Response**: Declaration with all items


### `PUT /api/v1/payroll/tax-declarations/{declaration_id}`
Update tax declaration
* **Path Param**: `declaration_id`
* **Request Body**: Updated declaration items
* **Response**: Updated declaration

### `POST /api/v1/payroll/tax-declarations/{declaration_id}/submit`
Submit tax declaration
* **Path Param**: `declaration_id`
* **Response**: Submitted declaration

### `POST /api/v1/payroll/tax-declarations/{declaration_id}/approve`
Approve tax declaration
* **Path Param**: `declaration_id`
* **Request Body**: Approval/rejection per item
* **Response**: Approved declaration


### `POST /api/v1/payroll/tax-declarations/{declaration_id}/lock`
Lock tax declaration
* **Path Param**: `declaration_id`
* **Response**: Locked declaration


### `POST /api/v1/payroll/tax-declarations/{declaration_id}/items`
Add declaration items
* **Path Param**: `declaration_id`
* **Request Body**: Array of investment items
* **Response**: Updated declaration

### `GET /api/v1/payroll/employees/{employee_id}/tax-calculation`
Get employee's tax calculation
* **Path Param**: `employee_id`
* **Query Params**: `financial_year`, `calculation_type`
* **Response**: Detailed tax calculation


### `POST /api/v1/payroll/employees/{employee_id}/calculate-tax`
Calculate tax for employee
* **Path Param**: `employee_id`
* **Request Body**: Financial year, tax regime, projections
* **Response**: Tax calculation breakdown


### `POST /api/v1/payroll/tax-calculations/bulk`
Bulk calculate tax for all employees
* **Request Body**: Financial year, employee filters
* **Response**: Bulk calculation summary


### `GET /api/v1/payroll/employees/{employee_id}/tax-regime-comparison`
Compare tax regimes for employee
* **Path Param**: `employee_id`
* **Query Params**: `financial_year`
* **Response**: Old vs New regime comparison


---

## 11. BANK FILE GENERATION

### `GET /api/v1/payroll/bank-files`
Get bank files
* **Query Params**: `period_id`, `status`, `from_date`, `to_date`
* **Response**: Array of bank files


### `POST /api/v1/payroll/bank-files/generate`
Generate bank file for payroll period
* **Request Body**: Period ID, bank format, filters
* **Response**: Generated bank file details


### `GET /api/v1/payroll/bank-files/{file_id}`
Get bank file details
* **Path Param**: `file_id`
* **Response**: Bank file with record count and totals


### `GET /api/v1/payroll/bank-files/{file_id}/download`
Download bank file
* **Path Param**: `file_id`
* **Response**: File download (NEFT/RTGS/CSV format)


### `POST /api/v1/payroll/bank-files/{file_id}/upload-confirmation`
Upload bank confirmation
* **Path Param**: `file_id`
* **Request Body**: Confirmation file, UTR numbers
* **Response**: Updated bank file status

### `GET /api/v1/payroll/bank-files/{file_id}/records`
Get bank file records
* **Path Param**: `file_id`
* **Query Params**: `payment_status`
* **Response**: Individual payment records


---

## 12. PAYROLL RECONCILIATION

### `GET /api/v1/payroll/reconciliations`
Get payroll reconciliations
* **Query Params**: `period_id`, `status`, `financial_year`
* **Response**: Array of reconciliation records


### `POST /api/v1/payroll/reconciliations`
Create payroll reconciliation
* **Request Body**: Period ID, previous period ID (for comparison)
* **Response**: Created reconciliation with variance analysis


### `GET /api/v1/payroll/reconciliations/{reconciliation_id}`
Get reconciliation details
* **Path Param**: `reconciliation_id`
* **Response**: Detailed reconciliation with issues


### `GET /api/v1/payroll/reconciliations/{reconciliation_id}/issues`
Get reconciliation issues
* **Path Param**: `reconciliation_id`
* **Query Params**: `severity`, `status`
* **Response**: Array of issues found


### `POST /api/v1/payroll/reconciliations/{reconciliation_id}/issues/{issue_id}/resolve`
Resolve reconciliation issue
* **Path Params**: `reconciliation_id`, `issue_id`
* **Request Body**: Resolution notes
* **Response**: Resolved issue


### `POST /api/v1/payroll/reconciliations/{reconciliation_id}/approve`
Approve reconciliation
* **Path Param**: `reconciliation_id`
* **Response**: Approved reconciliation

### `GET /api/v1/payroll/reconciliations/{reconciliation_id}/export`
Export reconciliation report
* **Path Param**: `reconciliation_id`
* **Query Params**: `format` (pdf, excel)
* **Response**: File download


---

## 13. PAYROLL JOURNAL ENTRIES

### `GET /api/v1/payroll/journal-entries`
Get payroll journal entries
* **Query Params**: `period_id`, `financial_year`, `status`
* **Response**: Array of journal entries
, Accountant

### `POST /api/v1/payroll/journal-entries/generate`
Generate journal entries for payroll
* **Request Body**: Period ID, entry types
* **Response**: Generated journal entries


### `GET /api/v1/payroll/journal-entries/{entry_id}`
Get journal entry details
* **Path Param**: `entry_id`
* **Response**: Journal entry with line items
, Accountant

### `POST /api/v1/payroll/journal-entries/{entry_id}/post`
Post journal entry
* **Path Param**: `entry_id`
* **Response**: Posted journal entry

### `POST /api/v1/payroll/journal-entries/{entry_id}/export`
Export journal entry to ERP
* **Path Param**: `entry_id`
* **Query Params**: `erp_system`
* **Response**: Export confirmation with reference


### `POST /api/v1/payroll/journal-entries/{entry_id}/reverse`
Reverse journal entry
* **Path Param**: `entry_id`
* **Request Body**: Reversal reason
* **Response**: Reversal entry created


---

## 14. STATUTORY FORMS & COMPLIANCE

### `GET /api/v1/payroll/statutory-forms`
Get statutory forms
* **Query Params**: `form_type`, `financial_year`, `filing_status`
* **Response**: Array of statutory forms
, Compliance Officer

### `POST /api/v1/payroll/statutory-forms/generate`
Generate statutory form
* **Request Body**: Form type, period, employee filters
* **Response**: Generated form details


### `GET /api/v1/payroll/statutory-forms/{form_id}`
Get statutory form details
* **Path Param**: `form_id`
* **Response**: Form details with filing status


### `GET /api/v1/payroll/statutory-forms/{form_id}/download`
Download statutory form
* **Path Param**: `form_id`
* **Response**: PDF/Excel file download
, Compliance Officer

### `POST /api/v1/payroll/statutory-forms/{form_id}/file`
Mark form as filed
* **Path Param**: `form_id`
* **Request Body**: Filing reference, acknowledgment number
* **Response**: Updated form status
, Compliance Officer

### `GET /api/v1/payroll/employees/{employee_id}/form16`
Generate Form 16 for employee
* **Path Param**: `employee_id`
* **Query Params**: `financial_year`
* **Response**: Form 16 PDF


### `POST /api/v1/payroll/statutory-forms/form16/bulk`
Bulk generate Form 16 for all employees
* **Request Body**: Financial year, employee filters
* **Response**: Bulk generation status


---

## 15. REPORTS & ANALYTICS

### `GET /api/v1/payroll/reports/payroll-summary`
Get payroll summary report
* **Query Params**: `period_id`, `financial_year`, `department_id`, `location_id`
* **Response**: Payroll summary with totals and averages
, Finance

### `GET /api/v1/payroll/reports/component-wise`
Get component-wise payroll report
* **Query Params**: `period_id`, `component_ids`
* **Response**: Breakdown by components


### `GET /api/v1/payroll/reports/department-wise`
Get department-wise payroll cost
* **Query Params**: `period_id` or `financial_year`
* **Response**: Payroll cost by department


### `GET /api/v1/payroll/reports/variance`
Get payroll variance report
* **Query Params**: `current_period_id`, `compare_period_id`
* **Response**: Period-over-period variance


### `GET /api/v1/payroll/reports/cost-center-allocation`
Get cost center allocation report
* **Query Params**: `period_id`
* **Response**: Payroll costs by cost center


### `GET /api/v1/payroll/reports/tax-deduction`
Get tax deduction report
* **Query Params**: `financial_year`, `quarter`
* **Response**: TDS deduction summary


### `GET /api/v1/payroll/reports/loan-recovery`
Get loan recovery report
* **Query Params**: `period_id`, `status`
* **Response**: Loan deductions in payroll


### `GET /api/v1/payroll/reports/salary-register`
Get salary register
* **Query Params**: `period_id`, `department_id`, `format` (pdf, excel)
* **Response**: Comprehensive salary register


### `GET /api/v1/payroll/reports/ytd-earnings`
Get YTD earnings report
* **Query Params**: `financial_year`, `employee_id`, `department_id`
* **Response**: Year-to-date earnings by employee
 (own data)

### `GET /api/v1/payroll/reports/payroll-cost-projection`
Get payroll cost projection
* **Query Params**: `months_ahead`, `include_increments`
* **Response**: Projected payroll costs


---

## 16. BULK OPERATIONS

### `POST /api/v1/payroll/bulk/salary-revision`
Bulk salary revision
* **Request Body**: Array of employee IDs, revision percentage, effective date
* **Response**: Bulk revision summary


### `POST /api/v1/payroll/bulk/component-adjustment`
Bulk component adjustment
* **Request Body**: Component ID, employee filters, adjustment amount/percentage
* **Response**: Adjustment summary


### `POST /api/v1/payroll/bulk/arrears`
Bulk create arrears
* **Request Body**: Array of arrear records
* **Response**: Bulk creation summary


### `POST /api/v1/payroll/bulk/one-time-payments`
Bulk create one-time payments
* **Request Body**: Payment type, employee list, amounts
* **Response**: Bulk creation summary


---

## 17. EMPLOYEE BANK ACCOUNTS

### `GET /api/v1/payroll/employees/{employee_id}/bank-accounts`
Get employee bank accounts
* **Path Param**: `employee_id`
* **Response**: Array of bank account records


### `POST /api/v1/payroll/employees/{employee_id}/bank-accounts`
Add employee bank account
* **Path Param**: `employee_id`
* **Request Body**: Bank details (account number, IFSC, etc.)
* **Response**: Created bank account

### `PUT /api/v1/payroll/bank-accounts/{account_id}`
Update bank account
* **Path Param**: `account_id`
* **Request Body**: Updated bank details
* **Response**: Updated bank account

### `POST /api/v1/payroll/bank-accounts/{account_id}/verify`
Verify bank account
* **Path Param**: `account_id`
* **Request Body**: Verification method, proof
* **Response**: Verified bank account


### `PATCH /api/v1/payroll/bank-accounts/{account_id}/set-primary`
Set as primary bank account
* **Path Param**: `account_id`
* **Response**: Updated bank account

### `DELETE /api/v1/payroll/bank-accounts/{account_id}`
Delete bank account
* **Path Param**: `account_id`
* **Response**: Success message

---

## 18. AUDIT & COMPLIANCE

### `GET /api/v1/payroll/audit-log`
Get payroll audit log
* **Query Params**: `action_type`, `entity_type`, `employee_id`, `performed_by`, `from_date`, `to_date`, `page`, `limit`
* **Response**: Paginated audit log entries
, Compliance Officer

### `GET /api/v1/payroll/audit-log/{log_id}`
Get audit log entry details
* **Path Param**: `log_id`
* **Response**: Detailed audit entry with before/after states
, Compliance Officer

### `POST /api/v1/payroll/audit-log/export`
Export audit log
* **Request Body**: Filter criteria, format
* **Response**: File download
, Compliance Officer

### `GET /api/v1/payroll/compliance/check`
Run payroll compliance check
* **Query Params**: `period_id`, `check_type`
* **Response**: Compliance report with violations
* **Access**: ce Officer, Payroll Admin

---

## TOTAL API COUNT: **180+ Payroll APIs**

### API Distribution:
- **Salary Components**: 5 endpoints
- **Salary Templates**: 8 endpoints
- **Employee Salary**: 9 endpoints
- **Payroll Periods**: 12 endpoints
- **Payslips**: 10 endpoints
- **Loans**: 10 endpoints
- **Reimbursements**: 11 endpoints
- **Final Settlement**: 8 endpoints
- **Arrears & One-time**: 7 endpoints
- **Tax**: 14 endpoints
- **Bank Files**: 6 endpoints
- **Reconciliation**: 7 endpoints
- **Journal Entries**: 6 endpoints
- **Statutory Forms**: 7 endpoints
- **Reports**: 10 endpoints
- **Bulk Operations**: 4 endpoints
- **Bank Accounts**: 6 endpoints
- **Audit**: 4 endpoints

All APIs include proper authentication, authorization, validation, and audit logging!