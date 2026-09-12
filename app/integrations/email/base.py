from abc import ABC, abstractmethod

class BaseEmailProvider(ABC):
    @abstractmethod
    async def send_email(self, recipient: str, subject: str, body: str) -> bool:
        pass