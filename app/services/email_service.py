import os
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Optional


class EmailConfigurationError(RuntimeError):
    pass


def _get_smtp_credentials() -> tuple[str, str, str, int]:
    """
    Read SMTP configuration from environment variables.

    These should be set in the local .env file or OS environment:
      - SMTP_SENDER_EMAIL
      - SMTP_SENDER_PASSWORD
      - SMTP_SERVER (default: smtp.gmail.com)
      - SMTP_PORT (default: 465)
    """
    sender_email = os.getenv("SMTP_SENDER_EMAIL")
    sender_password = os.getenv("SMTP_SENDER_PASSWORD")
    server = os.getenv("SMTP_SERVER", "smtp.gmail.com")
    port_raw = os.getenv("SMTP_PORT", "465")

    if not sender_email or not sender_password:
        raise EmailConfigurationError(
            "SMTP sender email or password is not configured. "
            "Set SMTP_SENDER_EMAIL and SMTP_SENDER_PASSWORD in your environment."
        )

    try:
        port = int(port_raw)
    except ValueError as exc:
        raise EmailConfigurationError(
            f"Invalid SMTP_PORT value: {port_raw!r}"
        ) from exc

    return sender_email, sender_password, server, port


def send_email(
    to_email: str,
    subject: str,
    body: str,
    reply_to: Optional[str] = None,
) -> None:
    """
    Send a plain-text email via SMTP using configured credentials.
    """
    sender_email, sender_password, smtp_server, smtp_port = _get_smtp_credentials()

    msg = MIMEMultipart()
    msg["From"] = sender_email
    msg["To"] = to_email
    msg["Subject"] = subject
    if reply_to:
        msg["Reply-To"] = reply_to

    msg.attach(MIMEText(body, "plain"))

    with smtplib.SMTP_SSL(smtp_server, smtp_port) as server:
        server.login(sender_email, sender_password)
        server.sendmail(sender_email, [to_email], msg.as_string())

