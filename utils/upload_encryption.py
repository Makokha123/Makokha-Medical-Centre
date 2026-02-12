"""utils/upload_encryption.py

Encrypt/decrypt user-uploaded files at rest.

Scope:
- Only for user uploads stored under the app's private `uploads/` directory.
- Static app assets (e.g., `/static/...` icons) are not encrypted.

Design goals:
- Backward compatible: if a file is not encrypted, it is served as-is.
- Safe key handling: key comes from env UPLOAD_ENCRYPTION_KEY or is persisted
  to instance/upload_encryption.key on first use.
- Atomic writes: encrypt in a temp file then replace.

File format (v1):
- MAGIC + nonce(12 bytes) + AESGCM(ciphertext||tag)

Note: This uses whole-file encryption; the app enforces upload size limits.
"""

from __future__ import annotations

import base64
import os
from typing import Optional

from cryptography.hazmat.primitives.ciphers.aead import AESGCM


_MAGIC = b"MMCUP1\n"
_NONCE_LEN = 12
_KEY_LEN = 32


def _b64url_decode(s: str) -> bytes:
    s = (s or "").strip()
    if not s:
        raise ValueError("empty")
    # Add padding if missing.
    pad = "=" * ((4 - (len(s) % 4)) % 4)
    return base64.urlsafe_b64decode(s + pad)


def _b64url_encode(b: bytes) -> str:
    return base64.urlsafe_b64encode(b).decode("utf-8").rstrip("=")


def get_upload_encryption_key_bytes() -> bytes:
    """Return the AES-GCM key bytes.

    Prefers env `UPLOAD_ENCRYPTION_KEY` (base64url), else loads/persists to
    `instance/upload_encryption.key`.
    """

    env_key = os.getenv("UPLOAD_ENCRYPTION_KEY")
    if env_key:
        key = _b64url_decode(env_key)
        if len(key) != _KEY_LEN:
            raise ValueError("UPLOAD_ENCRYPTION_KEY must decode to 32 bytes")
        return key

    instance_dir = os.path.join(os.getcwd(), "instance")
    os.makedirs(instance_dir, exist_ok=True)
    key_path = os.path.join(instance_dir, "upload_encryption.key")

    if os.path.exists(key_path):
        with open(key_path, "r", encoding="utf-8") as f:
            raw = f.read().strip()
        key = _b64url_decode(raw)
        if len(key) != _KEY_LEN:
            raise ValueError("instance/upload_encryption.key is invalid")
        return key

    key = os.urandom(_KEY_LEN)
    with open(key_path, "w", encoding="utf-8") as f:
        f.write(_b64url_encode(key))
    return key


def is_encrypted_blob(blob: bytes) -> bool:
    return isinstance(blob, (bytes, bytearray)) and blob.startswith(_MAGIC) and len(blob) > len(_MAGIC) + _NONCE_LEN


def encrypt_bytes(plaintext: bytes, *, key: Optional[bytes] = None) -> bytes:
    if plaintext is None:
        raise ValueError("plaintext is None")
    if is_encrypted_blob(plaintext):
        return bytes(plaintext)

    key_bytes = key or get_upload_encryption_key_bytes()
    aesgcm = AESGCM(key_bytes)
    nonce = os.urandom(_NONCE_LEN)
    ct = aesgcm.encrypt(nonce, plaintext, None)
    return _MAGIC + nonce + ct


def decrypt_bytes(blob: bytes, *, key: Optional[bytes] = None) -> bytes:
    if blob is None:
        raise ValueError("blob is None")
    if not is_encrypted_blob(blob):
        return bytes(blob)

    key_bytes = key or get_upload_encryption_key_bytes()
    aesgcm = AESGCM(key_bytes)

    nonce_start = len(_MAGIC)
    nonce_end = nonce_start + _NONCE_LEN
    nonce = blob[nonce_start:nonce_end]
    ct = blob[nonce_end:]
    return aesgcm.decrypt(nonce, ct, None)


def is_encrypted_file(path: str) -> bool:
    try:
        with open(path, "rb") as f:
            head = f.read(len(_MAGIC))
        return head == _MAGIC
    except Exception:
        return False


def encrypt_file_inplace(path: str) -> bool:
    """Encrypt a file in-place. Returns True if encryption happened."""

    if not path:
        return False

    try:
        if is_encrypted_file(path):
            return False

        with open(path, "rb") as f:
            plaintext = f.read()

        encrypted = encrypt_bytes(plaintext)
        tmp = path + ".tmp"
        with open(tmp, "wb") as f:
            f.write(encrypted)
        os.replace(tmp, path)
        return True
    except Exception:
        # Best-effort; leave original file untouched if anything goes wrong.
        try:
            tmp = path + ".tmp"
            if os.path.exists(tmp):
                os.remove(tmp)
        except Exception:
            pass
        return False


def decrypt_file_to_bytes(path: str) -> bytes:
    with open(path, "rb") as f:
        blob = f.read()
    return decrypt_bytes(blob)
