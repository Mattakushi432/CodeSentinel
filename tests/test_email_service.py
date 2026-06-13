"""Tests for app/services/email_service.py"""
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.email_service import send_magic_link, send_review_notification

# ---------------------------------------------------------------------------
# send_magic_link
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_send_magic_link_no_smtp_host_returns_silently(caplog):
    """When SMTP is not configured, the function logs a warning and returns."""
    with patch("app.services.email_service.get_settings") as mock_settings:
        settings = MagicMock()
        settings.smtp_host = ""
        mock_settings.return_value = settings

        # Should not raise
        await send_magic_link("user@example.com", "http://example.com/auth/verify?token=abc")

    assert True  # no exception raised


@pytest.mark.asyncio
async def test_send_magic_link_no_smtp_does_not_call_aiosmtplib():
    """When smtp_host is empty, aiosmtplib.send must not be called."""
    with patch("app.services.email_service.get_settings") as mock_settings, \
         patch("app.services.email_service.aiosmtplib") as mock_smtp:
        settings = MagicMock()
        settings.smtp_host = ""
        mock_settings.return_value = settings

        await send_magic_link("user@example.com", "http://localhost/verify?token=x")
        mock_smtp.send.assert_not_called()


@pytest.mark.asyncio
async def test_send_magic_link_with_smtp_calls_aiosmtplib():
    """When smtp_host is configured, aiosmtplib.send should be called once."""
    with patch("app.services.email_service.get_settings") as mock_settings, \
         patch("app.services.email_service.aiosmtplib") as mock_smtp:
        settings = MagicMock()
        settings.smtp_host = "smtp.example.com"
        settings.smtp_port = 587
        settings.smtp_user = "user"
        settings.smtp_password = "pass"
        settings.smtp_from = "noreply@example.com"
        mock_settings.return_value = settings
        mock_smtp.send = AsyncMock(return_value=None)

        await send_magic_link("recipient@example.com", "http://localhost/verify?token=tok")

        mock_smtp.send.assert_awaited_once()
        # Check call kwargs
        _, kwargs = mock_smtp.send.call_args
        assert kwargs["hostname"] == "smtp.example.com"
        assert kwargs["port"] == 587


@pytest.mark.asyncio
async def test_send_magic_link_smtp_error_propagates():
    """If aiosmtplib.send raises, the exception should propagate."""
    with patch("app.services.email_service.get_settings") as mock_settings, \
         patch("app.services.email_service.aiosmtplib") as mock_smtp:
        settings = MagicMock()
        settings.smtp_host = "smtp.example.com"
        settings.smtp_port = 587
        settings.smtp_user = ""
        settings.smtp_password = ""
        settings.smtp_from = "noreply@example.com"
        mock_settings.return_value = settings
        mock_smtp.send = AsyncMock(side_effect=ConnectionRefusedError("no connection"))

        with pytest.raises(ConnectionRefusedError):
            await send_magic_link("user@example.com", "http://localhost/verify?token=t")


# ---------------------------------------------------------------------------
# send_review_notification
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_send_review_notification_no_smtp_returns_silently():
    """When smtp_host is empty, function returns without error."""
    with patch("app.services.email_service.get_settings") as mock_settings:
        settings = MagicMock()
        settings.smtp_host = ""
        mock_settings.return_value = settings

        # Should not raise
        await send_review_notification(
            to_email="dev@example.com",
            pr_title="Fix auth bug",
            pr_url="https://github.com/owner/repo/pull/1",
            issue_count=3,
        )


@pytest.mark.asyncio
async def test_send_review_notification_no_smtp_does_not_call_aiosmtplib():
    with patch("app.services.email_service.get_settings") as mock_settings, \
         patch("app.services.email_service.aiosmtplib") as mock_smtp:
        settings = MagicMock()
        settings.smtp_host = ""
        mock_settings.return_value = settings

        await send_review_notification("dev@example.com", "My PR", "http://pr.url", 0)
        mock_smtp.send.assert_not_called()


@pytest.mark.asyncio
async def test_send_review_notification_with_smtp_calls_aiosmtplib():
    with patch("app.services.email_service.get_settings") as mock_settings, \
         patch("app.services.email_service.aiosmtplib") as mock_smtp:
        settings = MagicMock()
        settings.smtp_host = "smtp.example.com"
        settings.smtp_port = 587
        settings.smtp_user = "u"
        settings.smtp_password = "p"
        settings.smtp_from = "noreply@cs.dev"
        mock_settings.return_value = settings
        mock_smtp.send = AsyncMock(return_value=None)

        await send_review_notification(
            to_email="dev@example.com",
            pr_title="Add feature X",
            pr_url="https://github.com/owner/repo/pull/7",
            issue_count=2,
        )

        mock_smtp.send.assert_awaited_once()
        call_args = mock_smtp.send.call_args
        # First positional arg is the MIME message
        msg = call_args[0][0]
        assert "Add feature X" in msg["Subject"]


@pytest.mark.asyncio
async def test_send_review_notification_smtp_error_logged_not_raised():
    """SMTP failures for review notifications are swallowed (only logged)."""
    with patch("app.services.email_service.get_settings") as mock_settings, \
         patch("app.services.email_service.aiosmtplib") as mock_smtp:
        settings = MagicMock()
        settings.smtp_host = "smtp.example.com"
        settings.smtp_port = 587
        settings.smtp_user = ""
        settings.smtp_password = ""
        settings.smtp_from = "noreply@cs.dev"
        mock_settings.return_value = settings
        mock_smtp.send = AsyncMock(side_effect=ConnectionRefusedError("refused"))

        # Should NOT raise — review_notification swallows SMTP errors
        await send_review_notification("dev@example.com", "PR", "http://pr", 1)
