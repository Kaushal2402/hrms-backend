from xhtml2pdf import pisa
from io import BytesIO
from typing import Dict, Any

def generate_pdf(html_content: str) -> BytesIO:
    """Generates a PDF from HTML content using xhtml2pdf"""
    result = BytesIO()
    pisa_status = pisa.CreatePDF(BytesIO(html_content.encode("utf-8")), dest=result)
    if not pisa_status.err:
        return result
    return None

def get_payslip_html(data: Dict[str, Any]) -> str:
    """Generates a professional HTML template for the payslip"""
    # Format dates and currencies for the template
    basic = data.get('basic_salary', 0) or 0
    gross = data.get('gross_salary', 0) or 0
    total_earnings = data.get('total_earnings', 0) or 0
    total_deductions = data.get('total_deductions', 0) or 0
    tax = data.get('tax_deducted', 0) or 0
    lop = data.get('lop_amount', 0) or 0
    net = data.get('net_salary', 0) or 0
    
    html = f"""
    <html>
    <head>
        <style>
            @page {{
                size: A4;
                margin: 1.5cm;
            }}
            body {{
                font-family: Helvetica, Arial, sans-serif;
                color: #1f2937;
                line-height: 1.5;
                font-size: 11px;
            }}
            .header {{
                text-align: center;
                border-bottom: 3px solid #4f46e5;
                padding-bottom: 15px;
                margin-bottom: 25px;
            }}
            .company-name {{
                font-size: 22px;
                font-weight: bold;
                color: #4f46e5;
                text-transform: uppercase;
                letter-spacing: 1px;
            }}
            .payslip-title {{
                font-size: 16px;
                font-weight: bold;
                margin-top: 5px;
                color: #4b5563;
            }}
            .info-container {{
                margin-bottom: 30px;
            }}
            .info-table {{
                width: 100%;
                border-collapse: collapse;
            }}
            .info-table td {{
                padding: 6px 0;
                vertical-align: top;
            }}
            .label {{
                color: #6b7280;
                width: 110px;
                font-weight: bold;
                text-transform: uppercase;
                font-size: 9px;
            }}
            .value {{
                font-weight: bold;
                color: #111827;
            }}
            .main-table {{
                width: 100%;
                border-collapse: collapse;
                margin-bottom: 30px;
                border: 1px solid #e5e7eb;
            }}
            .main-table th {{
                background-color: #f9fafb;
                padding: 10px;
                text-align: left;
                font-size: 11px;
                border-bottom: 2px solid #e5e7eb;
                color: #374151;
                text-transform: uppercase;
            }}
            .main-table td {{
                padding: 10px;
                border-bottom: 1px solid #f3f4f6;
                vertical-align: top;
            }}
            .amount {{
                text-align: right;
                font-weight: bold;
                font-family: Courier, monospace;
            }}
            .total-row {{
                background-color: #f9fafb;
                font-weight: bold;
            }}
            .total-row td {{
                border-top: 2px solid #e5e7eb;
                color: #111827;
            }}
            .net-pay-box {{
                margin-top: 40px;
                padding: 20px;
                background-color: #f8fafc;
                border: 2px solid #4f46e5;
                border-radius: 8px;
                text-align: right;
            }}
            .net-pay-label {{
                font-size: 12px;
                color: #4f46e5;
                font-weight: bold;
                text-transform: uppercase;
                margin-bottom: 5px;
            }}
            .net-pay-value {{
                font-size: 28px;
                font-weight: bold;
                color: #111827;
            }}
            .footer {{
                position: fixed;
                bottom: 0;
                width: 100%;
                font-size: 9px;
                color: #9ca3af;
                text-align: center;
                border-top: 1px solid #f3f4f6;
                padding-top: 15px;
            }}
        </style>
    </head>
    <body>
        <div class="header">
            <div class="company-name">{data.get('organization_name', 'HRMS Enterprise')}</div>
            <div class="payslip-title">PAYSLIP FOR {data.get('period_name', 'N/A').upper()}</div>
        </div>

        <div class="info-container">
            <table class="info-table">
                <tr>
                    <td class="label">Employee Name</td>
                    <td class="value">{data.get('employee_name', 'N/A')}</td>
                    <td class="label">Employee Code</td>
                    <td class="value">{data.get('employee_code', 'N/A')}</td>
                </tr>
                <tr>
                    <td class="label">Department</td>
                    <td class="value">{data.get('department_name', 'N/A')}</td>
                    <td class="label">Designation</td>
                    <td class="value">{data.get('designation', 'N/A')}</td>
                </tr>
                <tr>
                    <td class="label">Payslip No.</td>
                    <td class="value">{data.get('payslip_number', 'N/A')}</td>
                    <td class="label">Payment Date</td>
                    <td class="value">{data.get('payment_date', 'N/A')}</td>
                </tr>
            </table>
        </div>

        <table class="main-table">
            <thead>
                <tr>
                    <th>Earnings Description</th>
                    <th class="amount">Amount</th>
                    <th>Deductions Description</th>
                    <th class="amount">Amount</th>
                </tr>
            </thead>
            <tbody>
                <tr>
                    <td>Basic Salary</td>
                    <td class="amount">{basic:,.2f}</td>
                    <td>Income Tax (TDS)</td>
                    <td class="amount">{tax:,.2f}</td>
                </tr>
                <tr>
                    <td>Allowances / HRA</td>
                    <td class="amount">{(total_earnings - basic):,.2f}</td>
                    <td>LOP Deductions</td>
                    <td class="amount">{lop:,.2f}</td>
                </tr>
                <tr>
                    <td>Other Earnings</td>
                    <td class="amount">0.00</td>
                    <td>Professional Tax / Other</td>
                    <td class="amount">{(total_deductions - tax - lop):,.2f}</td>
                </tr>
                <tr class="total-row">
                    <td>TOTAL EARNINGS (A)</td>
                    <td class="amount">{total_earnings:,.2f}</td>
                    <td>TOTAL DEDUCTIONS (B)</td>
                    <td class="amount">{total_deductions:,.2f}</td>
                </tr>
            </tbody>
        </table>

        <div class="net-pay-box">
            <div class="net-pay-label">Net Take Home Pay (A - B)</div>
            <div class="net-pay-value">{net:,.2f}</div>
        </div>

        <div class="footer">
            This is a computer-generated payslip and does not require a physical signature.<br/>
            Confidential Document &copy; 2026 {data.get('organization_name', 'HRMS Enterprise')}
        </div>
    </body>
    </html>
    """
    return html


def get_final_settlement_html(data: Dict[str, Any]) -> str:
    """Generates a professional HTML template for the Final Settlement Statement"""
    last_month_salary = data.get('last_month_salary', 0) or 0
    leave_encashment = data.get('leave_encashment_amount', 0) or 0
    leave_days = data.get('leave_balance_days', 0) or 0
    gratuity = data.get('gratuity_amount', 0) or 0
    bonus = data.get('bonus_amount', 0) or 0
    reimbursements = data.get('pending_reimbursements', 0) or 0
    recoveries = data.get('total_recoveries', 0) or 0
    net = data.get('net_settlement_amount', 0) or 0
    
    # Render optional notes boxes conditionally beforehand to avoid f-string syntax limitations in Python 3.10 and below
    notes_html = ""
    if data.get('notes'):
        notes_val = data.get('notes')
        notes_html = f"""
        <div class="notes-box">
            <div class="notes-title">Separation & Handover Notes</div>
            <div style="font-style: italic; color: #4b5563;">"{notes_val}"</div>
        </div>
        """

    approval_comments_html = ""
    if data.get('approval_comments'):
        app_val = data.get('approval_comments')
        approval_comments_html = f"""
        <div class="notes-box" style="background-color: #fef3c7; border-color: #f59e0b;">
            <div class="notes-title" style="color: #b45309;">Approval Comments</div>
            <div style="font-style: italic; color: #78350f;">"{app_val}"</div>
        </div>
        """

    payment_record_html = ""
    if data.get('payment_mode'):
        pay_mode = data.get('payment_mode')
        pay_ref = data.get('payment_reference') or '-'
        payment_record_html = f"""
        <div class="notes-box" style="background-color: #ecfdf5; border-color: #10b981;">
            <div class="notes-title" style="color: #047857;">Payment Record</div>
            <div style="font-weight: bold; color: #065f46;">
                Paid Via: {pay_mode} | Reference: {pay_ref}
            </div>
        </div>
        """

    html = f"""
    <html>
    <head>
        <style>
            @page {{
                size: A4;
                margin: 1.5cm;
            }}
            body {{
                font-family: Helvetica, Arial, sans-serif;
                color: #1f2937;
                line-height: 1.5;
                font-size: 11px;
            }}
            .header {{
                text-align: center;
                border-bottom: 3px solid #4f46e5;
                padding-bottom: 15px;
                margin-bottom: 25px;
            }}
            .company-name {{
                font-size: 22px;
                font-weight: bold;
                color: #4f46e5;
                text-transform: uppercase;
                letter-spacing: 1px;
            }}
            .payslip-title {{
                font-size: 16px;
                font-weight: bold;
                margin-top: 5px;
                color: #4b5563;
            }}
            .info-container {{
                margin-bottom: 30px;
            }}
            .info-table {{
                width: 100%;
                border-collapse: collapse;
            }}
            .info-table td {{
                padding: 6px 0;
                vertical-align: top;
            }}
            .label {{
                color: #6b7280;
                width: 120px;
                font-weight: bold;
                text-transform: uppercase;
                font-size: 9px;
            }}
            .value {{
                font-weight: bold;
                color: #111827;
            }}
            .section-header {{
                font-size: 12px;
                font-weight: bold;
                color: #4f46e5;
                margin-top: 20px;
                margin-bottom: 10px;
                border-bottom: 1px solid #e5e7eb;
                padding-bottom: 5px;
                text-transform: uppercase;
            }}
            .main-table {{
                width: 100%;
                border-collapse: collapse;
                margin-bottom: 30px;
                border: 1px solid #e5e7eb;
            }}
            .main-table th {{
                background-color: #f9fafb;
                padding: 10px;
                text-align: left;
                font-size: 11px;
                border-bottom: 2px solid #e5e7eb;
                color: #374151;
                text-transform: uppercase;
            }}
            .main-table td {{
                padding: 10px;
                border-bottom: 1px solid #f3f4f6;
                vertical-align: top;
            }}
            .amount {{
                text-align: right;
                font-weight: bold;
                font-family: Courier, monospace;
            }}
            .total-row {{
                background-color: #f9fafb;
                font-weight: bold;
            }}
            .total-row td {{
                border-top: 2px solid #e5e7eb;
                color: #111827;
            }}
            .net-pay-box {{
                margin-top: 40px;
                padding: 20px;
                background-color: #f8fafc;
                border: 2px solid #4f46e5;
                border-radius: 8px;
                text-align: right;
            }}
            .net-pay-label {{
                font-size: 12px;
                color: #4f46e5;
                font-weight: bold;
                text-transform: uppercase;
                margin-bottom: 5px;
            }}
            .net-pay-value {{
                font-size: 28px;
                font-weight: bold;
                color: #111827;
            }}
            .notes-box {{
                margin-top: 20px;
                padding: 12px;
                background-color: #f9fafb;
                border: 1px dashed #d1d5db;
                border-radius: 6px;
            }}
            .notes-title {{
                font-weight: bold;
                font-size: 9px;
                color: #4b5563;
                text-transform: uppercase;
                margin-bottom: 4px;
            }}
            .footer {{
                position: fixed;
                bottom: 0;
                width: 100%;
                font-size: 9px;
                color: #9ca3af;
                text-align: center;
                border-top: 1px solid #f3f4f6;
                padding-top: 15px;
            }}
        </style>
    </head>
    <body>
        <div class="header">
            <div class="company-name">{data.get('organization_name', 'HRMS Enterprise')}</div>
            <div class="payslip-title">FINAL SETTLEMENT STATEMENT</div>
        </div>

        <div class="info-container">
            <div class="section-header">Employment & Separation Details</div>
            <table class="info-table">
                <tr>
                    <td class="label">Employee Name</td>
                    <td class="value">{data.get('employee_name', 'N/A')}</td>
                    <td class="label">Employee Code</td>
                    <td class="value">{data.get('employee_code', 'N/A')}</td>
                </tr>
                <tr>
                    <td class="label">Department</td>
                    <td class="value">{data.get('department_name', 'N/A')}</td>
                    <td class="label">Designation</td>
                    <td class="value">{data.get('designation', 'N/A')}</td>
                </tr>
                <tr>
                    <td class="label">Settlement No.</td>
                    <td class="value">{data.get('settlement_number', 'N/A')}</td>
                    <td class="label">Settlement Date</td>
                    <td class="value">{data.get('settlement_date', 'N/A')}</td>
                </tr>
                <tr>
                    <td class="label">Last Working Day</td>
                    <td class="value">{data.get('last_working_date', 'N/A')}</td>
                    <td class="label">Separation Type</td>
                    <td class="value">{data.get('separation_type', 'N/A')}</td>
                </tr>
                <tr>
                    <td class="label">Service Tenure</td>
                    <td class="value" colspan="3">{data.get('tenure_summary', 'N/A')}</td>
                </tr>
            </table>
        </div>

        <div class="section-header">Financial Breakdowns</div>
        <table class="main-table">
            <thead>
                <tr>
                    <th>Earnings Description</th>
                    <th class="amount">Amount</th>
                    <th>Recoveries / Deductions</th>
                    <th class="amount">Amount</th>
                </tr>
            </thead>
            <tbody>
                <tr>
                    <td>Last Month Remuneration</td>
                    <td class="amount">{last_month_salary:,.2f}</td>
                    <td>Recoveries & Deductions</td>
                    <td class="amount">{recoveries:,.2f}</td>
                </tr>
                <tr>
                    <td>Leave Encashment ({leave_days} days)</td>
                    <td class="amount">{leave_encashment:,.2f}</td>
                    <td>Tax Deductions (TDS)</td>
                    <td class="amount">{data.get('tax_deducted', 0):,.2f}</td>
                </tr>
                <tr>
                    <td>Gratuity / Separation Pay</td>
                    <td class="amount">{gratuity:,.2f}</td>
                    <td>Notice Pay Recovery</td>
                    <td class="amount">{data.get('notice_pay_recovery', 0):,.2f}</td>
                </tr>
                <tr>
                    <td>Reimbursements & Bonus</td>
                    <td class="amount">{(bonus + reimbursements):,.2f}</td>
                    <td>Other Recoveries</td>
                    <td class="amount">0.00</td>
                </tr>
                <tr class="total-row">
                    <td>TOTAL EARNINGS (A)</td>
                    <td class="amount">{(last_month_salary + leave_encashment + gratuity + bonus + reimbursements):,.2f}</td>
                    <td>TOTAL DEDUCTIONS (B)</td>
                    <td class="amount">{(recoveries + data.get('tax_deducted', 0) + data.get('notice_pay_recovery', 0)):,.2f}</td>
                </tr>
            </tbody>
        </table>

        <div class="net-pay-box">
            <div class="net-pay-label">Total Net Settlement Payout (A - B)</div>
            <div class="net-pay-value">{net:,.2f}</div>
        </div>

        {notes_html}

        {approval_comments_html}

        {payment_record_html}

        <div class="footer">
            This is a computer-generated final settlement statement and does not require a physical signature.<br/>
            Confidential Document &copy; 2026 {data.get('organization_name', 'HRMS Enterprise')}
        </div>
    </body>
    </html>
    """
    return html


def get_appraisal_record_html(data: Dict[str, Any]) -> str:
    """Generates a professional HTML template for the Performance Appraisal Record"""
    promotion_section = ""
    if data.get('promotion_recommended'):
        promotion_section = f"""
        <div class="section-header">Promotion Recommendation</div>
        <table class="info-table">
            <tr>
                <td class="label">Recommended</td>
                <td class="value" style="color: #d97706; font-weight: bold;">YES</td>
                <td class="label">Target Grade</td>
                <td class="value">{data.get('promotion_recommended_to_grade', 'N/A')}</td>
            </tr>
            <tr>
                <td class="label">Recommendation Notes</td>
                <td class="value" colspan="3" style="font-weight: normal; color: #4b5563;">{data.get('promotion_notes', 'None')}</td>
            </tr>
        </table>
        """

    acknowledgment_section = ""
    ack_status = "YES" if data.get('acknowledged_by_employee') else "NO"
    ack_color = "#10b981" if data.get('acknowledged_by_employee') else "#ef4444"
    disagreement_html = ""
    if data.get('employee_disagreement_reason'):
        disagreement_html = f"""
        <tr>
            <td class="label" style="color: #ef4444;">Disagreement Reason</td>
            <td class="value" colspan="3" style="font-weight: normal; color: #991b1b; background-color: #fef2f2; padding: 8px; border-radius: 4px;">{data.get('employee_disagreement_reason')}</td>
        </tr>
        """
    acknowledgment_section = f"""
    <div class="section-header">Employee Acknowledgment</div>
    <table class="info-table">
        <tr>
            <td class="label">Acknowledged</td>
            <td class="value" style="color: {ack_color}; font-weight: bold;">{ack_status}</td>
            <td class="label">Date Acknowledged</td>
            <td class="value">{data.get('employee_acknowledged_at', 'N/A')}</td>
        </tr>
        {disagreement_html}
    </table>
    """

    calibration_section = ""
    if data.get('calibrated_score') is not None or data.get('final_rating_label'):
        calibration_section = f"""
        <tr>
            <td class="label" style="color: #4f46e5;">Calibrated Score</td>
            <td class="value" style="color: #4f46e5; font-size: 14px;">{data.get('calibrated_score', 'N/A')}</td>
            <td class="label" style="color: #4f46e5;">Final Rating</td>
            <td class="value" style="color: #4f46e5; font-size: 14px;">{data.get('final_rating_label', 'N/A')}</td>
        </tr>
        <tr>
            <td class="label">Calibration Notes</td>
            <td class="value" colspan="3" style="font-weight: normal; color: #4b5563;">{data.get('calibration_notes', 'None')}</td>
        </tr>
        """

    html = f"""
    <html>
    <head>
        <style>
            @page {{
                size: A4;
                margin: 1.5cm;
            }}
            body {{
                font-family: Helvetica, Arial, sans-serif;
                color: #1f2937;
                line-height: 1.5;
                font-size: 11px;
            }}
            .header {{
                text-align: center;
                border-bottom: 3px solid #4f46e5;
                padding-bottom: 15px;
                margin-bottom: 25px;
            }}
            .company-name {{
                font-size: 22px;
                font-weight: bold;
                color: #4f46e5;
                text-transform: uppercase;
                letter-spacing: 1px;
            }}
            .payslip-title {{
                font-size: 16px;
                font-weight: bold;
                margin-top: 5px;
                color: #4b5563;
            }}
            .info-container {{
                margin-bottom: 20px;
            }}
            .info-table {{
                width: 100%;
                border-collapse: collapse;
                margin-bottom: 15px;
            }}
            .info-table td {{
                padding: 6px 4px;
                vertical-align: top;
                border-bottom: 1px solid #f3f4f6;
            }}
            .label {{
                color: #6b7280;
                width: 120px;
                font-weight: bold;
                text-transform: uppercase;
                font-size: 9px;
            }}
            .value {{
                font-weight: bold;
                color: #111827;
            }}
            .section-header {{
                font-size: 12px;
                font-weight: bold;
                color: #4f46e5;
                margin-top: 25px;
                margin-bottom: 10px;
                border-bottom: 1px solid #e5e7eb;
                padding-bottom: 5px;
                text-transform: uppercase;
            }}
            .score-card-table {{
                width: 100%;
                border-collapse: collapse;
                margin-top: 10px;
                border: 1px solid #e5e7eb;
            }}
            .score-card-table th {{
                background-color: #f9fafb;
                padding: 8px;
                text-align: left;
                font-size: 10px;
                border-bottom: 2px solid #e5e7eb;
                color: #374151;
                text-transform: uppercase;
            }}
            .score-card-table td {{
                padding: 10px 8px;
                border-bottom: 1px solid #e5e7eb;
            }}
            .footer {{
                position: fixed;
                bottom: 0;
                width: 100%;
                font-size: 9px;
                color: #9ca3af;
                text-align: center;
                border-top: 1px solid #f3f4f6;
                padding-top: 15px;
            }}
        </style>
    </head>
    <body>
        <div class="header">
            <div class="company-name">{data.get('organization_name', 'HRMS Enterprise')}</div>
            <div class="payslip-title">PERFORMANCE APPRAISAL REPORT</div>
            <div style="font-size: 12px; color: #6b7280; margin-top: 5px;">{data.get('cycle_name', 'N/A')}</div>
        </div>

        <div class="info-container">
            <div class="section-header">Employee Information</div>
            <table class="info-table">
                <tr>
                    <td class="label">Employee Name</td>
                    <td class="value">{data.get('employee_name', 'N/A')}</td>
                    <td class="label">Employee Code</td>
                    <td class="value">{data.get('employee_code', 'N/A')}</td>
                </tr>
                <tr>
                    <td class="label">Department</td>
                    <td class="value">{data.get('department_name', 'N/A')}</td>
                    <td class="label">Designation</td>
                    <td class="value">{data.get('designation', 'N/A')}</td>
                </tr>
                <tr>
                    <td class="label">Email Address</td>
                    <td class="value">{data.get('employee_email', 'N/A')}</td>
                    <td class="label">Appraisal Status</td>
                    <td class="value" style="color: #4b5563;">{data.get('status', 'N/A')}</td>
                </tr>
                <tr>
                    <td class="label">Reporting Manager</td>
                    <td class="value" colspan="3">{data.get('manager_name', 'N/A')}</td>
                </tr>
            </table>
        </div>

        <div class="section-header">Evaluation Summary</div>
        <table class="score-card-table">
            <thead>
                <tr>
                    <th>Evaluation Aspect</th>
                    <th>Self Assessment</th>
                    <th>Manager Review</th>
                </tr>
            </thead>
            <tbody>
                <tr>
                    <td><strong>Goal Score</strong></td>
                    <td>{data.get('self_goal_score', 'N/A')}</td>
                    <td>{data.get('manager_goal_score', 'N/A')}</td>
                </tr>
                <tr>
                    <td><strong>Competency Score</strong></td>
                    <td>{data.get('self_competency_score', 'N/A')}</td>
                    <td>{data.get('manager_competency_score', 'N/A')}</td>
                </tr>
                <tr>
                    <td><strong>Overall Rating Score</strong></td>
                    <td><strong>{data.get('self_overall_score', 'N/A')}</strong></td>
                    <td><strong>{data.get('manager_overall_score', 'N/A')}</strong></td>
                </tr>
                <tr>
                    <td><strong>Rating Description</strong></td>
                    <td><span style="font-weight: bold;">{data.get('self_rating_label', 'N/A')}</span></td>
                    <td><span style="font-weight: bold;">{data.get('manager_rating_label', 'N/A')}</span></td>
                </tr>
            </tbody>
        </table>

        {"" if not (data.get('calibrated_score') is not None or data.get('final_rating_label') or data.get('calibration_notes')) else f'''
        <div class="section-header">Calibration Details</div>
        <table class="info-table">
            {calibration_section}
        </table>
        '''}

        {promotion_section}

        {acknowledgment_section}

        <div class="footer">
            This is a computer-generated performance appraisal report.<br/>
            Confidential Document &copy; 2026 {data.get('organization_name', 'HRMS Enterprise')}
        </div>
    </body>
    </html>
    """
    return html

