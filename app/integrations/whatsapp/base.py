# app/integrations/whatsapp/base.py
from abc import ABC, abstractmethod

class BaseWhatsAppProvider(ABC):
    @abstractmethod
    async def send_message(self, phone: str, message: str) -> bool:
        pass