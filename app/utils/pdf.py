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
