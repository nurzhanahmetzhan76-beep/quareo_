"""Шифрование чувствительных данных (API-ключи пользователей) через Fernet."""
from cryptography.fernet import Fernet, InvalidToken
from retailpool.config import settings

_fernet = Fernet(settings.ENCRYPTION_KEY.encode())

def encrypt_secret(plain: str | None) -> str | None:
    """Зашифровать строку перед записью в БД."""
    if not plain:
        return plain
    return _fernet.encrypt(plain.encode()).decode()

def decrypt_secret(token: str | None) -> str | None:
    """Расшифровать строку из БД. Старые незашифрованные значения вернёт как есть."""
    if not token:
        return token
    try:
        return _fernet.decrypt(token.encode()).decode()
    except InvalidToken:
        return token
