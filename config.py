import base64
import os
from dotenv import load_dotenv
from cryptography.fernet import Fernet, InvalidToken
from flask import current_app

load_dotenv()

class Config:
    DEBUG = False
    TESTING = False
    
    # Security
    SESSION_COOKIE_SECURE = True
    REMEMBER_COOKIE_SECURE = True
    SESSION_COOKIE_HTTPONLY = True
    REMEMBER_COOKIE_HTTPONLY = True
    
    # Core Application Settings
    SECRET_KEY = os.getenv("SECRET_KEY")
    SQLALCHEMY_DATABASE_URI = os.getenv('DATABASE_URL', 'sqlite:///clinic.db')
    SQLALCHEMY_TRACK_MODIFICATIONS = os.getenv('SQLALCHEMY_TRACK_MODIFICATIONS', 'false').lower() == 'true'
    
    # File Handling
    UPLOAD_FOLDER = os.getenv('UPLOAD_FOLDER')
    BACKUP_FOLDER = os.getenv('BACKUP_FOLDER')
    MAX_CONTENT_LENGTH = int(os.getenv('MAX_CONTENT_LENGTH', 16 * 1024 * 1024))  # 16MB default
    
    # Security Settings
    SESSION_COOKIE_SECURE = os.getenv('SESSION_COOKIE_SECURE', 'true').lower() == 'true'
    SESSION_COOKIE_SAMESITE = os.getenv('SESSION_COOKIE_SAMESITE', 'Lax')
    PREFERRED_URL_SCHEME = os.getenv('PREFERRED_URL_SCHEME', 'https')
    
    # Encryption
    FERNET_KEY = os.getenv('FERNET_KEY')
    
    # Email Configuration
    MAIL_SERVER = os.getenv('MAIL_SERVER', 'smtp-relay.brevo.com')
    MAIL_PORT = int(os.getenv('MAIL_PORT', 587))
    MAIL_USE_TLS = os.getenv('MAIL_USE_TLS', 'true').lower() == 'true'
    MAIL_USERNAME = os.getenv('BREVO_EMAIL')
    MAIL_PASSWORD = os.getenv('BREVO_SMTP_KEY')
    MAIL_DEFAULT_SENDER = os.getenv('MAIL_DEFAULT_SENDER', 'no-reply@yourdomain.com')
    
    # Security Extensions
    SECURITY_PASSWORD_SALT = os.getenv('SECURITY_PASSWORD_SALT')
    
    # API Configuration
    DEEPSEEK_CONFIG = {
        "api_key": os.getenv("DEEPSEEK_API_KEY"),
        "base_url": os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com"),
        "timeout": float(os.getenv("DEEPSEEK_TIMEOUT", 30.0)),
        "max_retries": int(os.getenv("DEEPSEEK_MAX_RETRIES", 3))
    }
    
    @classmethod
    def init_fernet(cls, app):
        """Initialize Fernet encryption with proper error handling"""
        try:
            key = os.getenv('FERNET_KEY')
            if not key:
                # Fernet.generate_key() already returns a valid 44-char key
                key = Fernet.generate_key().decode()
                app.logger.warning("No FERNET_KEY in environment - generating new key")
                os.environ['FERNET_KEY'] = key
            
            if len(key) != 44:
                raise ValueError("Invalid Fernet key length - must be 44 character URL-safe base64 string")
                
            cls.fernet = Fernet(key.encode())
            cls.FERNET_KEY = key
            app.logger.info("Fernet encryption initialized successfully")
            app.config['FERNET_KEY'] = cls.FERNET_KEY
            
        except Exception as e:
            app.logger.error(f"Fernet initialization failed: {str(e)}")
            new_key = Fernet.generate_key().decode()
            cls.fernet = Fernet(new_key.encode())
            cls.FERNET_KEY = new_key
            os.environ['FERNET_KEY'] = new_key
            app.config['FERNET_KEY'] = new_key
            app.logger.warning("Generated new Fernet key due to initialization error")

    @classmethod
    def encrypt_data(cls, data):
        """Encrypt data with proper error handling"""
        if not data or not isinstance(data, str):
            return ""
            
        try:
            if cls.fernet is None:
                raise ValueError("Fernet not initialized")
            return cls.fernet.encrypt(data.encode()).decode()
        except InvalidToken as e:
            current_app.logger.error(f"Encryption failed - invalid token: {str(e)}")
            return ""
        except Exception as e:
            current_app.logger.error(f"Encryption failed: {str(e)}")
            return ""

    @classmethod
    def decrypt_data(cls, encrypted_data):
        """Decrypt data with proper error handling"""
        if not encrypted_data or not isinstance(encrypted_data, str):
            return ""
            
        try:
            if cls.fernet is None:
                raise ValueError("Fernet not initialized")
            return cls.fernet.decrypt(encrypted_data.encode()).decode()
        except InvalidToken as e:
            current_app.logger.error(f"Decryption failed - invalid token: {str(e)}")
            cls.init_fernet(current_app)
            try:
                return cls.fernet.decrypt(encrypted_data.encode()).decode()
            except:
                return "[Decryption Error: Invalid Token]"
        except Exception as e:
            current_app.logger.error(f"Decryption failed: {str(e)}")
            return "[Decryption Error]"

    @staticmethod
    def encrypt_data_static(data):
        """Static method version for model access"""
        return Config.encrypt_data(data)

    @staticmethod
    def decrypt_data_static(encrypted_data):
        """Static method version for model access"""
        return Config.decrypt_data(encrypted_data)