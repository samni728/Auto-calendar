import base64
import hashlib
import secrets
from datetime import UTC, datetime, timedelta

from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError
from cryptography.fernet import Fernet

from .config import get_settings

password_hasher = PasswordHasher()


def hash_password(password: str) -> str:
    return password_hasher.hash(password)


def verify_password(password_hash: str, password: str) -> bool:
    try:
        return password_hasher.verify(password_hash, password)
    except VerifyMismatchError:
        return False


def create_secret_token(length: int = 32) -> str:
    return secrets.token_urlsafe(length)


def token_hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def session_expiry() -> datetime:
    return datetime.now(UTC) + timedelta(days=get_settings().session_days)


def _fernet() -> Fernet:
    key = get_settings().app_encryption_key.encode()
    try:
        return Fernet(key)
    except ValueError as exc:
        raise RuntimeError("APP_ENCRYPTION_KEY must be a valid Fernet key") from exc


def encrypt_secret(value: str) -> str:
    return _fernet().encrypt(value.encode()).decode()


def decrypt_secret(value: str | None) -> str:
    if not value:
        return ""
    return _fernet().decrypt(value.encode()).decode()


def pkce_challenge(verifier: str) -> str:
    digest = hashlib.sha256(verifier.encode()).digest()
    return base64.urlsafe_b64encode(digest).rstrip(b"=").decode()
