"""Encryption utilities for vault sync.

Uses PBKDF2-SHA256 for key derivation and AES-256-GCM for encryption.
Mirrors the server and plugin crypto implementations for cross-client
compatibility.
"""

import hashlib
import os

from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.primitives import hashes

_KDF_ITERATIONS = 600_000
_KEY_LENGTH = 32  # 256 bits
_NONCE_LENGTH = 12  # 96 bits, standard for AES-GCM


def derive_key(passphrase: str, salt: str) -> bytes:
    """Derive a 32-byte encryption key from a passphrase and hex salt.

    Uses PBKDF2-SHA256 with 600 000 iterations.
    """
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=_KEY_LENGTH,
        salt=bytes.fromhex(salt),
        iterations=_KDF_ITERATIONS,
    )
    return kdf.derive(passphrase.encode("utf-8"))


def encrypt(key: bytes, plaintext: bytes) -> bytes:
    """Encrypt *plaintext* with AES-256-GCM.

    Returns ``nonce || ciphertext`` (12 + len(plaintext) + 16 bytes).
    """
    nonce = os.urandom(_NONCE_LENGTH)
    aesgcm = AESGCM(key)
    ciphertext = aesgcm.encrypt(nonce, plaintext, None)
    return nonce + ciphertext


def decrypt(key: bytes, data: bytes) -> bytes:
    """Decrypt data produced by :func:`encrypt`.

    Expects the first 12 bytes to be the nonce followed by the GCM
    ciphertext (including the 16-byte auth tag).
    """
    nonce = data[:_NONCE_LENGTH]
    ciphertext = data[_NONCE_LENGTH:]
    aesgcm = AESGCM(key)
    return aesgcm.decrypt(nonce, ciphertext, None)


def generate_salt() -> str:
    """Return 32 random bytes encoded as a hex string."""
    return os.urandom(32).hex()


def hash_key(key: bytes) -> str:
    """Return the SHA-256 hex digest of *key*.

    Used for server-side passphrase verification without exposing the
    actual encryption key.
    """
    return hashlib.sha256(key).hexdigest()
