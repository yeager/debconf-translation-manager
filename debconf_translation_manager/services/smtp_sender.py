"""SMTP email sender for submitting translations."""

from __future__ import annotations

import logging
import smtplib
from email.mime.application import MIMEApplication
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path

from debconf_translation_manager.services.settings import Settings

log = logging.getLogger(__name__)


def send_translation_email(
    to: str,
    cc: str,
    subject: str,
    body: str,
    po_file_path: str,
) -> tuple[bool, str]:
    """Send translation email with PO file attachment.

    Returns (success, message).
    """
    settings = Settings.get()

    from_addr = settings["email_from"] or settings["translator_email"]
    if not from_addr:
        return False, "No sender email configured"

    smtp_host = settings["smtp_host"]
    smtp_port = settings["smtp_port"]
    if not smtp_host:
        return False, "No SMTP server configured"

    msg = MIMEMultipart()
    msg["From"] = from_addr
    msg["To"] = to
    if cc:
        msg["Cc"] = cc
    msg["Subject"] = subject

    msg.attach(MIMEText(body, "plain", "utf-8"))

    # Attach PO file
    po_path = Path(po_file_path)
    if po_path.exists():
        with open(po_path, "rb") as f:
            attachment = MIMEApplication(f.read(), Name=po_path.name)
        attachment["Content-Disposition"] = f'attachment; filename="{po_path.name}"'
        msg.attach(attachment)
    else:
        return False, f"PO file not found: {po_file_path}"

    try:
        if settings["smtp_use_tls"]:
            server = smtplib.SMTP(smtp_host, smtp_port)
            server.starttls()
        else:
            server = smtplib.SMTP(smtp_host, smtp_port)

        smtp_user = settings["smtp_user"]
        smtp_pass = settings["smtp_password"]
        if smtp_user and smtp_pass:
            server.login(smtp_user, smtp_pass)

        recipients = [to]
        if cc:
            recipients.extend(addr.strip() for addr in cc.split(","))

        server.sendmail(from_addr, recipients, msg.as_string())
        server.quit()
        return True, "Email sent successfully"
    except Exception as exc:
        log.error("SMTP error: %s", exc)
        return False, str(exc)
