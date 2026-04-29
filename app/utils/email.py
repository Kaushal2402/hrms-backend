import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from app.core.config import settings

def send_email(email_to: str, subject: str, html_content: str):
    if not settings.SMTP_HOST or not settings.SMTP_USER:
        print(f"SMTP settings not configured. Mock sending email to {email_to}")
        print(f"Subject: {subject}")
        print(f"Content: {html_content}")
        return

    msg = MIMEMultipart()
    msg['From'] = f"{settings.EMAILS_FROM_NAME} <{settings.EMAILS_FROM_EMAIL}>"
    msg['To'] = email_to
    msg['Subject'] = subject

    msg.attach(MIMEText(html_content, 'html'))

    try:
        server = smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT)
        if settings.SMTP_TLS:
            server.starttls()
        server.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
        server.sendmail(settings.EMAILS_FROM_EMAIL, email_to, msg.as_string())
        server.quit()
    except Exception as e:
        print(f"Failed to send email: {e}")

def send_otp_email(email_to: str, otp: str, org_name: str):
    subject = "Verify your Organization - HRMS"
    html_content = f"""
    <html>
        <body style="font-family: Arial, sans-serif; padding: 20px;">
            <h2>Welcome to HRMS, {org_name}!</h2>
            <p>Thank you for registering. Please use the verification code below to activate your account:</p>
            <h3 style="background-color: #f4f4f4; padding: 10px; display: inline-block;">{otp}</h3>
            <p>This code will expire in 10 minutes.</p>
            <p>If you didn't request this, please ignore this email.</p>
        </body>
    </html>
    """
    send_email(email_to, subject, html_content)

def send_welcome_email(email_to: str, org_name: str, password: str):
    subject = "Welcome to HRMS - Account Activated"
    html_content = f"""
    <html>
        <body style="font-family: Arial, sans-serif; padding: 20px;">
            <h2>Welcome {org_name}!</h2>
            <p>Your account has been successfully verified and activated.</p>
            <p>Your login credentials are:</p>
            <p><strong>Email:</strong> {email_to}</p>
            <p><strong>Password:</strong> {password}</p>
            <p>Please change your password after your first login.</p>
            <br>
            <p>Best regards,<br>The HRMS Team</p>
        </body>
    </html>
    """
    send_email(email_to, subject, html_content)

def send_reset_password_email(email_to: str, token: str):
    subject = "Reset Your Password - HRMS"
    # Assuming frontend URL structure
    reset_link = f"http://127.0.0.1:3000/reset-password?token={token}" 
    html_content = f"""
    <html>
        <body style="font-family: Arial, sans-serif; padding: 20px;">
            <h2>Password Reset Request</h2>
            <p>You requested a password reset. Click the link below to set a new password:</p>
            <a href="{reset_link}" style="padding: 10px 20px; background-color: #007bff; color: white; text-decoration: none; border-radius: 5px;">Reset Password</a>
            <p>This link is valid for 1 hour.</p>
            <p>If you didn't request this, you can safely ignore this email.</p>
        </body>
    </html>
    """
    send_email(email_to, subject, html_content)

def send_set_password_email(email_to: str, token: str, first_name: str):
    subject = "Complete Your Account Setup - HRMS"
    # Assuming frontend URL structure
    set_link = f"http://127.0.0.1:3000/set-password?token={token}" 
    html_content = f"""
    <html>
        <body style="font-family: Arial, sans-serif; padding: 20px;">
            <h2>Welcome to the Team, {first_name}!</h2>
            <p>Your account has been created on HRMS. Click the button below to set your password and get started:</p>
            <a href="{set_link}" style="padding: 10px 20px; background-color: #28a745; color: white; text-decoration: none; border-radius: 5px; display: inline-block;">Set Password</a>
            <p>This invitation link is valid for 24 hours.</p>
            <p>Best regards,<br>The HRMS Team</p>
        </body>
    </html>
    """
    send_email(email_to, subject, html_content)
