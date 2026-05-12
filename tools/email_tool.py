import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from langchain_core.tools import tool

from config import settings
from guardrails.tool_guards import check_rate_limit, GuardrailError
from guardrails.confirmation_gate import request_confirmation, ConfirmationDeniedError


@tool
def send_email_tool(to: str, subject: str, body: str) -> str:
    """Send an email to the given address with the specified subject and body.
    Uses SMTP settings from environment variables (EMAIL_* vars)."""
    try:
        check_rate_limit("send_email_tool")
        request_confirmation("Send email", f"To: {to} | Subject: {subject}")

        msg = MIMEMultipart()
        msg["From"] = settings.email_from
        msg["To"] = to
        msg["Subject"] = subject
        msg.attach(MIMEText(body, "plain"))

        with smtplib.SMTP(settings.email_smtp_host, settings.email_smtp_port) as smtp:
            smtp.ehlo()
            smtp.starttls()
            smtp.login(settings.email_username, settings.email_password)
            smtp.sendmail(settings.email_from, to, msg.as_string())

        return f"Email sent to {to}"
    except GuardrailError as e:
        return f"[Blocked] {e}"
    except ConfirmationDeniedError as e:
        return f"[Cancelled] {e}"
    except Exception as e:
        return f"Failed to send email: {e}"
