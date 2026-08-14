import logging

from app.core.config import settings

logger = logging.getLogger("app.email")
logger.setLevel(logging.INFO)
if not logger.handlers:
    logger.addHandler(logging.StreamHandler())


def send_password_reset_email(to_email: str, raw_token: str) -> None:
    """Dev stub: logs the reset link instead of sending real email.

    Swap this for a real provider (SES, SendGrid, etc.) in production.
    """
    reset_link = f"{settings.frontend_base_url}/reset-password?token={raw_token}"
    logger.info("Password reset link for %s: %s", to_email, reset_link)
