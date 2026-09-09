import base64
import os
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from app.core.config import settings


class CredentialEncryption:
    """
    AES-256-GCM encryption engine for storing third-party CRM API keys and OAuth tokens.
    Uses a 12-byte (96-bit) IV/nonce per encryption call to prevent IV reuse attacks.
    Output format: 12-byte IV + ciphertext + 16-byte authentication tag.
    """

    def __init__(self) -> None:
        raw_key = base64.urlsafe_b64decode(settings.MASTER_ENCRYPTION_KEY)
        if len(raw_key) != 32:
            raise ValueError(f"Master encryption key must be 32 bytes for AES-256. Found: {len(raw_key)} bytes.")
        self._aesgcm = AESGCM(raw_key)

    def encrypt(self, plaintext: str) -> bytes:
        """Encrypts plaintext string into binary payload containing IV and auth tag."""
        if not plaintext:
            raise ValueError("Cannot encrypt empty value.")
        
        # 96-bit nonce as recommended by NIST SP 800-38D
        nonce = os.urandom(12)
        ciphertext = self._aesgcm.encrypt(nonce, plaintext.encode("utf-8"), None)
        # Prepend nonce directly to the ciphertext for extraction during decryption
        return nonce + ciphertext

    def decrypt(self, encrypted_payload: bytes) -> str:
        """Decrypts encrypted binary payload, verifying the authentication tag."""
        if len(encrypted_payload) < 28:  # 12 bytes nonce + 16 bytes auth tag minimum
            raise ValueError("Invalid encrypted payload size: corrupted data.")
        
        nonce = encrypted_payload[:12]
        ciphertext = encrypted_payload[12:]
        
        decrypted_bytes = self._aesgcm.decrypt(nonce, ciphertext, None)
        return decrypted_bytes.decode("utf-8")


encryptor = CredentialEncryption()