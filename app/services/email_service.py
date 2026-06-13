import logging
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

import aiosmtplib

from app.config import get_settings

logger = logging.getLogger(__name__)


async def send_magic_link(to_email: str, magic_url: str) -> None:
    settings = get_settings()
    if not settings.smtp_host:
        logger.warning("SMTP not configured. Magic link for %s: %s", to_email, magic_url)
        return

    msg = MIMEMultipart("alternative")
    msg["Subject"] = "Your CodeSentinel login link"
    msg["From"] = settings.smtp_from
    msg["To"] = to_email

    text_body = f"Click to login to CodeSentinel:\n{magic_url}\n\nThis link expires in 15 minutes."
    html_body = f"""
    <html><body>
    <h2>CodeSentinel Login</h2>
    <p><a href="{magic_url}" style="background:#2563eb;color:white;padding:12px 24px;border-radius:6px;text-decoration:none;display:inline-block;">Login to CodeSentinel</a></p>
    <p style="color:#6b7280;font-size:14px;">This link expires in 15 minutes. If you didn't request this, ignore this email.</p>
    </body></html>
    """

    msg.attach(MIMEText(text_body, "plain"))
    msg.attach(MIMEText(html_body, "html"))

    try:
        await aiosmtplib.send(
            msg,
            hostname=settings.smtp_host,
            port=settings.smtp_port,
            username=settings.smtp_user or None,
            password=settings.smtp_password or None,
            start_tls=True,
        )
        logger.info("Magic link sent to %s", to_email)
    except Exception as exc:
        logger.error("Failed to send magic link to %s: %s", to_email, exc)
        raise


async def send_review_notification(to_email: str, pr_title: str, pr_url: str, issue_count: int) -> None:
    settings = get_settings()
    if not settings.smtp_host:
        return

    msg = MIMEMultipart("alternative")
    msg["Subject"] = f"CodeSentinel: Review complete for '{pr_title}'"
    msg["From"] = settings.smtp_from
    msg["To"] = to_email

    body = (
        f"Review complete for PR: {pr_title}\n"
        f"Issues found: {issue_count}\n"
        f"View PR: {pr_url}\n"
    )
    msg.attach(MIMEText(body, "plain"))

    try:
        await aiosmtplib.send(
            msg,
            hostname=settings.smtp_host,
            port=settings.smtp_port,
            username=settings.smtp_user or None,
            password=settings.smtp_password or None,
            start_tls=True,
        )
    except Exception as exc:
        logger.warning("Failed to send review notification: %s", exc)
