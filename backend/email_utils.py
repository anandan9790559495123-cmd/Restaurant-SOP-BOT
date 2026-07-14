import smtplib
import os
import random
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from dotenv import load_dotenv

load_dotenv()

SMTP_EMAIL = os.getenv("SMTP_EMAIL", "")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD", "")


def generate_otp():
    """Generate a 6-digit OTP code."""
    return str(random.randint(100000, 999999))


def send_otp_email(to_email, otp_code):
    """Send an OTP email using Gmail SMTP."""
    if not SMTP_EMAIL or not SMTP_PASSWORD:
        raise ValueError("SMTP credentials not configured. Please set SMTP_EMAIL and SMTP_PASSWORD in .env")

    msg = MIMEMultipart("alternative")
    msg["Subject"] = "Reset Password"
    msg["From"] = SMTP_EMAIL
    msg["To"] = to_email

    # Plain text fallback
    text_content = f"""
Password Reset Request

Your One-Time Password (OTP) is: {otp_code}

This code is valid for 10 minutes. Do not share this code with anyone.

If you did not request this, please ignore this email.

— Restaurant SOP Bot System
    """

    # Clean, light-themed HTML email to avoid spam folder placement
    html_content = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
    </head>
    <body style="margin: 0; padding: 0; background-color: #f4f6f9; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif;">
        <table width="100%" cellpadding="0" cellspacing="0" style="background-color: #f4f6f9; padding: 40px 20px;">
            <tr>
                <td align="center">
                    <table width="480" cellpadding="0" cellspacing="0" style="background-color: #ffffff; border-radius: 8px; border: 1px solid #e1e4e8; overflow: hidden; box-shadow: 0 4px 12px rgba(0, 0, 0, 0.05);">
                        <!-- Header -->
                        <tr>
                            <td style="padding: 30px 40px 20px; text-align: center; background-color: #ffffff;">
                                <h1 style="color: #1a1f36; font-size: 22px; margin: 0; font-weight: 600;">Restaurant SOP Portal</h1>
                            </td>
                        </tr>
                        <!-- Content -->
                        <tr>
                            <td style="padding: 20px 40px 30px;">
                                <h2 style="color: #3c4257; font-size: 16px; margin: 0 0 10px; font-weight: 600;">Password Reset OTP</h2>
                                <p style="color: #697386; font-size: 14px; line-height: 1.5; margin: 0 0 20px;">
                                    Use the security verification code below to reset your password. This code is valid for 10 minutes.
                                </p>
                                <!-- OTP Box -->
                                <div style="background-color: #f7fafc; border: 1px solid #e3e8ee; border-radius: 6px; padding: 20px; text-align: center; margin-bottom: 20px;">
                                    <span style="color: #4f566b; font-size: 11px; text-transform: uppercase; letter-spacing: 1.5px; font-weight: 600; display: block; margin-bottom: 8px;">Verification Code</span>
                                    <div style="font-size: 32px; font-weight: 700; color: #1a1f36; letter-spacing: 6px; font-family: monospace;">{otp_code}</div>
                                </div>
                                <p style="color: #697386; font-size: 13px; line-height: 1.5; margin: 0 0 8px;">
                                    If you did not initiate this request, please disregard this email. Your password remains secure.
                                </p>
                            </td>
                        </tr>
                        <!-- Footer -->
                        <tr>
                            <td style="padding: 20px 40px 30px; text-align: center; background-color: #fcfdfe; border-top: 1px solid #f2f4f6;">
                                <p style="color: #8792a2; font-size: 12px; margin: 0;">
                                    Secured by Restaurant SOP Bot System
                                </p>
                            </td>
                        </tr>
                    </table>
                </td>
            </tr>
        </table>
    </body>
    </html>
    """

    msg.attach(MIMEText(text_content, "plain"))
    msg.attach(MIMEText(html_content, "html"))

    try:
        server = smtplib.SMTP("smtp.gmail.com", 587)
        server.starttls()
        server.login(SMTP_EMAIL, SMTP_PASSWORD)
        server.sendmail(SMTP_EMAIL, to_email, msg.as_string())
        server.quit()
        return True
    except Exception as e:
        print(f"Email send error: {e}")
        raise e
