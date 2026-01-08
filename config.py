import os
from typing import List, Optional, Sequence, Tuple

from dotenv import load_dotenv
from cryptography.fernet import Fernet, InvalidToken
from flask import current_app

load_dotenv()


def _get_env(name: str, default: Optional[str] = None, required: bool = False) -> str:
    """
    Get an environment variable. If required=True and missing, raise RuntimeError.
    """
    val = os.getenv(name, default)
    if required and not val:
        raise RuntimeError(f"Missing required environment variable: {name}")
    return val or ""


def _parse_bool(val: Optional[str], default: bool = False) -> bool:
    if val is None:
        return default
    return str(val).strip().lower() in ("1", "true", "yes", "y", "on")


def _parse_int(val: Optional[str], default: int) -> int:
    try:
        return int(str(val).strip())
    except Exception:
        return default


def _parse_csv(val: Optional[str]) -> List[str]:
    if not val:
        return []
    s = val.strip()
    if s.startswith("[") and s.endswith("]"):  # tolerate Python-like list strings
        s = s[1:-1]
    items = [p.strip().strip("'").strip('"') for p in s.split(",")]
    return [i for i in items if i]


def _validate_fernet_key(key: str, var_name: str) -> str:
    """
    Validate that the key is a canonical Fernet key: 44-char urlsafe base64 encoding of 32 bytes.
    """
    k = (key or "").strip()
    try:
        Fernet(k.encode())  # will raise if invalid/incorrect padding
        if len(k) != 44:
            raise ValueError("Invalid Fernet key length; expected 44 characters")
        return k
    except Exception as e:
        raise RuntimeError(f"{var_name} is not a valid Fernet key. Generate with Fernet.generate_key(). Error: {e}") from e


class Config:
    """
    Central application configuration with strict environment handling and encryption helpers.

    Usage:
      app.config.from_object(Config)
      Config.init_fernet(app)
    """

    # Basic flags
    DEBUG = _parse_bool(_get_env("DEBUG", "false"))
    TESTING = _parse_bool(_get_env("TESTING", "false"))

    @staticmethod
    def _is_production() -> bool:
        """Best-effort environment detection.

        Treat Render and explicit production flags as production.
        """
        if _parse_bool(os.getenv("PRODUCTION"), False):
            return True
        if os.getenv("RENDER"):
            return True
        if (os.getenv("FLASK_ENV") or "").strip().lower() == "production":
            return True
        if (os.getenv("ENV") or "").strip().lower() == "production":
            return True
        return False

    # Cookies/security headers
    SESSION_COOKIE_SECURE = _parse_bool(_get_env("SESSION_COOKIE_SECURE", "true"))
    REMEMBER_COOKIE_SECURE = SESSION_COOKIE_SECURE
    SESSION_COOKIE_HTTPONLY = True
    REMEMBER_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = _get_env("SESSION_COOKIE_SAMESITE", "Lax")
    PREFERRED_URL_SCHEME = _get_env("PREFERRED_URL_SCHEME", "https")

    # In production, SECRET_KEY and SECURITY_PASSWORD_SALT must be provided. For development, fall back to ephemeral keys with warnings.
    SECRET_KEY = _get_env("SECRET_KEY")
    SECURITY_PASSWORD_SALT = _get_env("SECURITY_PASSWORD_SALT")

    # Use a stable SQLite path by default under instance/
    SQLALCHEMY_DATABASE_URI = _get_env("DATABASE_URL", "sqlite:///instance/clinic.db")
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # File handling
    UPLOAD_FOLDER = _get_env("UPLOAD_FOLDER", "static/uploads")
    BACKUP_FOLDER = _get_env("BACKUP_FOLDER", "backups")
    MAX_CONTENT_LENGTH = _parse_int(_get_env("MAX_CONTENT_LENGTH", str(16 * 1024 * 1024)), 16 * 1024 * 1024)  # 16MB

    # Email (Brevo/Gmail)
    MAIL_SERVER = _get_env("MAIL_SERVER", "smtp-relay.brevo.com")
    MAIL_PORT = _parse_int(_get_env("MAIL_PORT", "587"), 587)
    MAIL_USE_TLS = _parse_bool(_get_env("MAIL_USE_TLS", "true"), True)
    MAIL_USERNAME = _get_env("MAIL_USERNAME") or _get_env("BREVO_EMAIL")
    MAIL_PASSWORD = _get_env("MAIL_PASSWORD") or _get_env("BREVO_SMTP_KEY")
    MAIL_DEFAULT_SENDER = _get_env("MAIL_DEFAULT_SENDER") or (MAIL_USERNAME or "no-reply@yourdomain.com")

    # Password reset token expiration (seconds)
    RESET_TOKEN_EXPIRATION = _parse_int(_get_env("RESET_TOKEN_EXPIRATION", "3600"), 3600)

    # AI / LLMs
    DEEPSEEK_API_KEY = _get_env("DEEPSEEK_API_KEY")
    DEEPSEEK_CONFIG = {
        "api_key": DEEPSEEK_API_KEY,
        "base_url": _get_env("DEEPSEEK_BASE_URL", "https://api.deepseek.com"),
        "timeout": float(_get_env("DEEPSEEK_TIMEOUT", "30")),
        "max_retries": _parse_int(_get_env("DEEPSEEK_MAX_RETRIES", "3"), 3),
    }

    # Dosage AI generation (admin dosage/monographs)
    # These are intentionally separate from DEEPSEEK_CONFIG because dosage generation can be much longer.
    DOSAGE_AI_TIMEOUT_SECONDS = float(_get_env("DOSAGE_AI_TIMEOUT_SECONDS", "1200"))
    # Interactive UI-triggered job time budget (polling job). Keep finite to avoid runaway background threads.
    AI_DOSAGE_JOB_MAX_RUN_SECONDS = _parse_int(_get_env("AI_DOSAGE_JOB_MAX_RUN_SECONDS", "1200"), 1200)

    # Encryption keys (set by init_fernet)
    FERNET_KEY: Optional[str] = None
    BACKUP_ENCRYPTION_KEY: Optional[str] = None
    fernet: Optional[Fernet] = None
    legacy_fernets: Tuple[Fernet, ...] = tuple()

    # Backups
    AWS_BACKUP_BUCKET = _get_env("AWS_BACKUP_BUCKET")
    BACKUP_TABLES = _parse_csv(_get_env("BACKUP_TABLES", ""))  # optional whitelist

    @classmethod
    def init_secrets(cls, app):
        """
        Ensure SECRET_KEY and SECURITY_PASSWORD_SALT are set. In production, require them; in development, generate ephemeral ones.
        """
        if not cls.SECRET_KEY:
            if not cls._is_production() or cls.DEBUG or cls.TESTING:
                import secrets
                cls.SECRET_KEY = secrets.token_hex(64)
                app.logger.warning("SECRET_KEY missing; generated ephemeral dev key. Do NOT use in production.")
            else:
                raise RuntimeError("SECRET_KEY is required in production.")
        if not cls.SECURITY_PASSWORD_SALT:
            if not cls._is_production() or cls.DEBUG or cls.TESTING:
                import secrets
                cls.SECURITY_PASSWORD_SALT = secrets.token_hex(64)
                app.logger.warning("SECURITY_PASSWORD_SALT missing; generated ephemeral dev salt. Do NOT use in production.")
            else:
                raise RuntimeError("SECURITY_PASSWORD_SALT is required in production.")
        # Reflect back into app.config so extensions see the values.
        app.config["SECRET_KEY"] = cls.SECRET_KEY
        app.config["SECURITY_PASSWORD_SALT"] = cls.SECURITY_PASSWORD_SALT

    @classmethod
    def init_fernet(cls, app):
        """
        Initialize Fernet encryption with strict validation.
        - Require FERNET_KEY in production.
        - Support LEGACY_FERNET_KEYS for decryption-only (comma-separated), useful during key rotation.
        - Never auto-generate or rotate keys silently at runtime in production.
        """
        key_env = _get_env("FERNET_KEY")
        legacy_keys_env = _get_env("LEGACY_FERNET_KEYS", "")  # CSV of older keys allowed for decryption

        if not key_env:
            if not cls._is_production() or cls.DEBUG or cls.TESTING:
                # Development convenience: generate ephemeral key but warn loudly.
                key_env = Fernet.generate_key().decode()
                app.logger.warning("FERNET_KEY missing; generated ephemeral dev key. Data encrypted now will be unreadable next restart.")
            else:
                raise RuntimeError("FERNET_KEY is required in production.")

        key = _validate_fernet_key(key_env, "FERNET_KEY")
        cls.fernet = Fernet(key.encode())
        cls.FERNET_KEY = key

        legacy: List[Fernet] = []
        for lk in _parse_csv(legacy_keys_env):
            try:
                lk_valid = _validate_fernet_key(lk, "LEGACY_FERNET_KEYS")
                legacy.append(Fernet(lk_valid.encode()))
            except Exception as e:
                app.logger.error(f"Ignoring invalid legacy Fernet key: {e}")

        cls.legacy_fernets = tuple(legacy)
        app.config["FERNET_KEY"] = cls.FERNET_KEY
        app.logger.info("Fernet initialized. Legacy keys count: %d", len(cls.legacy_fernets))

        # Backup encryption key (separate from app data key)
        backup_key_env = _get_env("BACKUP_ENCRYPTION_KEY")
        if not backup_key_env:
            if not cls._is_production() or cls.DEBUG or cls.TESTING:
                backup_key_env = Fernet.generate_key().decode()
                app.logger.warning("BACKUP_ENCRYPTION_KEY missing; generated ephemeral dev key. Do NOT use in production.")
            else:
                raise RuntimeError("BACKUP_ENCRYPTION_KEY is required in production.")
        cls.BACKUP_ENCRYPTION_KEY = _validate_fernet_key(backup_key_env, "BACKUP_ENCRYPTION_KEY")
        if cls.BACKUP_ENCRYPTION_KEY == cls.FERNET_KEY:
            app.logger.warning("BACKUP_ENCRYPTION_KEY equals FERNET_KEY; use separate keys for separation of duties.")

    @classmethod
    def encrypt_data(cls, data: Optional[str]) -> str:
        """
        Encrypt a string. Returns empty string on invalid input or errors.
        """
        if not data or not isinstance(data, str):
            return ""
        if not cls.fernet:
            raise RuntimeError("Fernet not initialized. Call Config.init_fernet(app) at startup.")
        try:
            return cls.fernet.encrypt(data.encode()).decode()
        except Exception as e:
            current_app.logger.error(f"Encryption failed: {e}")
            return ""

    @classmethod
    def decrypt_data(cls, encrypted_data: Optional[str]) -> str:
        """
        Decrypt a string using the active key, falling back to legacy keys if provided.
        Returns placeholder text on failure to avoid leaking internals.
        """
        if not encrypted_data or not isinstance(encrypted_data, str):
            return ""
        if not cls.fernet:
            raise RuntimeError("Fernet not initialized. Call Config.init_fernet(app) at startup.")
        try:
            return cls.fernet.decrypt(encrypted_data.encode()).decode()
        except InvalidToken:
            # Try legacy keys (if any), decryption-only
            for f in cls.legacy_fernets:
                try:
                    return f.decrypt(encrypted_data.encode()).decode()
                except Exception:
                    continue
            current_app.logger.error("Decryption failed: Invalid token for current and legacy keys.")
            return "[Decryption Error: Invalid Token]"
        except Exception as e:
            current_app.logger.error(f"Decryption failed: {e}")
            return "[Decryption Error]"

    @staticmethod
    def encrypt_data_static(data: Optional[str]) -> str:
        return Config.encrypt_data(data)

    @staticmethod
    def decrypt_data_static(encrypted_data: Optional[str]) -> str:
        return Config.decrypt_data(encrypted_data)

    @classmethod
    def build_backup_config(cls) -> dict:
        """
        Construct backup configuration used by the backup service.
        tables_to_backup: optional whitelist from env BACKUP_TABLES; services should intersect with existing tables.
        """
        return {
            "local_storage_path": cls.BACKUP_FOLDER,
            "s3_bucket": cls.AWS_BACKUP_BUCKET or "",
            "encryption_key": cls.BACKUP_ENCRYPTION_KEY,
            "tables_to_backup": cls.BACKUP_TABLES,  # may be empty; treat as "all non-system tables"
        }