# app/integrations/email/smtp.py
import structlog
import httpx
from app.integrations.email.base import BaseEmailProvider

logger = structlog.get_logger()

class SMTPProvider(BaseEmailProvider):
    async def send_email(self, recipient: str, subject: str, body: str) -> bool:
        logger.info("email.smtp.sent_mock", recipient=recipient, subject=subject)
        return True