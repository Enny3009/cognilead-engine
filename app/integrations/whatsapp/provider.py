# app/integrations/whatsapp/provider.py
import structlog
from app.integrations.whatsapp.base import BaseWhatsAppProvider

logger = structlog.get_logger()

class WhatsAppProvider(BaseWhatsAppProvider):
    async def send_message(self, phone: str, message: str) -> bool:
        logger.info("whatsapp.provider.sent_mock", phone=phone, message=message[:50])
        return True