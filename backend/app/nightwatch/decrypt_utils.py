"""Fernet key encryption for API keys.

Copied from GlucoAssist research.py pattern. Uses APP_SECRET_KEY to derive a
stable Fernet key via SHA-256 → base64 urlsafe.
"""

from __future__ import annotations

import base64
import hashlib

from cryptography.fernet import Fernet


def _get_secret_key() -> bytes:
    """Derive a stable Fernet key from APP_SECRET_KEY environment variable."""
    import os

    raw = os.environ.get("APP_SECRET_KEY", "default-secret-key-for-local-development")
    key = base64.urlsafe_b64encode(hashlib.sha256(raw.encode()).digest())
    return key


def _fernet() -> Fernet:
    """Return a Fernet instance derived from APP_SECRET_KEY."""
    return Fernet(_get_secret_key())


def encrypt_api_key(plaintext: str) -> str:
    """Encrypt a plaintext API key using Fernet.

    Args:
        plaintext: The unencrypted API key string.

    Returns:
        The encrypted key as a string.
    """
    return _fernet().encrypt(plaintext.encode()).decode()


def decrypt_api_key(ciphertext: str) -> str:
    """Decrypt a Fernet-encrypted API key.

    Args:
        ciphertext: The encrypted API key string.

    Returns:
        The decrypted plaintext API key.
    """
    return _fernet().decrypt(ciphertext.encode()).decode()
