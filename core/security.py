from cryptography.fernet import Fernet
from core.config import settings
import base64
import hashlib


class TokenEncryption:
    def __init__(self):
        key = settings.ENCRYPTION_KEY.encode()
        if len(key) != 44:
            key = base64.urlsafe_b64encode(hashlib.sha256(key).digest())
        self.cipher = Fernet(key)

    def encrypt(self, plaintext: str) -> str:
        if not plaintext:
            return ""
        return self.cipher.encrypt(plaintext.encode()).decode()

    def decrypt(self, ciphertext: str) -> str:
        if not ciphertext:
            return ""
        return self.cipher.decrypt(ciphertext.encode()).decode()


token_encryption = TokenEncryption()
