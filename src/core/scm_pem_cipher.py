import base64
import json
import os
from typing import Any

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from src.config import get_settings
from src.services.exceptions.source_control_exception import (
    InvalidSourceControlEncryptionKeyError,
    SourceControlEncryptionKeyNotConfiguredError,
)


class ScmAuthCipher:
    """Encrypts and decrypts SCM authentication configuration."""

    # Fields that should be encrypted per auth type
    SENSITIVE_FIELDS = {
        "github_app": ["pem"],
        "gitlab_pat": ["access_token"],
    }

    @classmethod
    def encrypt_auth_config(cls, auth_config: dict[str, Any]) -> dict[str, Any]:
        """Encrypt sensitive fields in auth config."""
        auth_type = auth_config.get("type")
        if not auth_type:
            return auth_config

        sensitive_fields = cls.SENSITIVE_FIELDS.get(auth_type, [])
        encrypted_config = auth_config.copy()

        for field in sensitive_fields:
            if field in encrypted_config and encrypted_config[field]:
                encrypted_config[f"encrypted_{field}"] = cls._encrypt(encrypted_config[field])
                del encrypted_config[field]

        return encrypted_config

    @classmethod
    def decrypt_auth_config(cls, auth_config: dict[str, Any]) -> dict[str, Any]:
        """Decrypt sensitive fields in auth config."""
        auth_type = auth_config.get("type")
        if not auth_type:
            return auth_config

        sensitive_fields = cls.SENSITIVE_FIELDS.get(auth_type, [])
        decrypted_config = auth_config.copy()

        for field in sensitive_fields:
            encrypted_field = f"encrypted_{field}"
            if encrypted_field in decrypted_config and decrypted_config[encrypted_field]:
                decrypted_config[field] = cls._decrypt(decrypted_config[encrypted_field])
                del decrypted_config[encrypted_field]

        return decrypted_config

    @classmethod
    def _encrypt(cls, plaintext: str) -> str:
        key = cls._get_key()
        nonce = os.urandom(12)
        cipher = AESGCM(key)
        encrypted = cipher.encrypt(nonce, plaintext.encode("utf-8"), None)
        return base64.b64encode(nonce + encrypted).decode("utf-8")

    @classmethod
    def _decrypt(cls, encrypted_text: str) -> str:
        key = cls._get_key()

        try:
            payload = base64.b64decode(encrypted_text)
        except Exception as exc:
            raise InvalidSourceControlEncryptionKeyError() from exc

        nonce = payload[:12]
        cipher_text = payload[12:]
        cipher = AESGCM(key)
        decrypted = cipher.decrypt(nonce, cipher_text, None)
        return decrypted.decode("utf-8")

    @classmethod
    def _get_key(cls) -> bytes:
        settings = get_settings()
        encryption_key = (
            settings.source_control.encryption_key
            if settings.source_control is not None
            else None
        )
        if not encryption_key:
            raise SourceControlEncryptionKeyNotConfiguredError()

        try:
            key = base64.b64decode(encryption_key)
        except Exception as exc:
            raise InvalidSourceControlEncryptionKeyError() from exc

        if len(key) not in (16, 24, 32):
            raise InvalidSourceControlEncryptionKeyError()

        return key


# Backward compatibility alias
ScmPemCipher = ScmAuthCipher
