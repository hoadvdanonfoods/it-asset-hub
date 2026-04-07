import base64
import hashlib
import hmac
import os

from cryptography.fernet import Fernet

from app.config import SECRET_KEY

ITERATIONS = 390000
SALT_BYTES = 16

# Derive a consistent 32-byte base64url key from SECRET_KEY
_fernet_key = base64.urlsafe_b64encode(hashlib.sha256(SECRET_KEY.encode()).digest())
_cipher_suite = Fernet(_fernet_key)


def encrypt_resource_password(plain_text: str | None) -> str | None:
    if not plain_text:
        return plain_text
    if plain_text.startswith('aes:'):
        return plain_text
    encrypted = _cipher_suite.encrypt(plain_text.encode('utf-8')).decode('utf-8')
    return f"aes:{encrypted}"


def decrypt_resource_password(encrypted_text: str | None) -> str | None:
    if not encrypted_text:
        return encrypted_text
    if not encrypted_text.startswith('aes:'):
        return encrypted_text
    try:
        token = encrypted_text[4:]
        return _cipher_suite.decrypt(token.encode('utf-8')).decode('utf-8')
    except Exception:
        return encrypted_text

SALT_BYTES = 16


def hash_password(password: str) -> str:
    salt = os.urandom(SALT_BYTES)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, ITERATIONS)
    return f"pbkdf2_sha256${ITERATIONS}${base64.b64encode(salt).decode()}${base64.b64encode(digest).decode()}"


def verify_password(password: str, stored_value: str | None) -> bool:
    if not stored_value:
        return False
    if not stored_value.startswith("pbkdf2_sha256$"):
        return hmac.compare_digest(stored_value, password)
    try:
        _, iterations, salt_b64, digest_b64 = stored_value.split("$", 3)
        salt = base64.b64decode(salt_b64.encode())
        expected = base64.b64decode(digest_b64.encode())
        actual = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, int(iterations))
        return hmac.compare_digest(actual, expected)
    except Exception:
        return False
