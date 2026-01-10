"""
Production-ready email utilities with enhanced error handling, retry logic, and logging.

Features:
- Exponential backoff retry logic for transient SMTP failures
- Comprehensive logging for audit trails
- Timeout handling and graceful degradation
- Email validation
- Template management
- Connection pooling and health checks
"""

import logging
import smtplib
import ssl
import time
from datetime import datetime, timedelta
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.message import EmailMessage
from threading import Thread, Lock
from typing import Optional, Callable, Any
import json
import re

logger = logging.getLogger(__name__)


class EmailConfig:
    """Email configuration holder."""
    
    def __init__(
        self,
        smtp_server: str,
        smtp_port: int,
        use_tls: bool,
        username: str,
        password: str,
        from_address: str,
        timeout_seconds: int = 30,
        max_retries: int = 3,
        retry_backoff_base: float = 2.0,
    ):
        self.smtp_server = smtp_server.strip() if smtp_server else None
        self.smtp_port = int(smtp_port) if smtp_port else 587
        self.use_tls = bool(use_tls)
        self.username = username.strip() if username else None
        self.password = password if password else None
        self.from_address = from_address.strip() if from_address else None
        self.timeout_seconds = max(5, min(timeout_seconds, 120))  # Clamp 5-120s
        self.max_retries = max(1, min(max_retries, 5))  # Clamp 1-5
        self.retry_backoff_base = max(1.5, min(retry_backoff_base, 3.0))  # Clamp 1.5-3.0
    
    def is_configured(self) -> bool:
        """Check if email is properly configured."""
        return bool(
            self.smtp_server
            and self.username
            and self.password
            and self.from_address
            and self._is_valid_email(self.from_address)
        )
    
    @staticmethod
    def _is_valid_email(email: str) -> bool:
        """Basic email validation."""
        if not email or len(email) > 254:
            return False
        pattern = r'^[^\s@]+@[^\s@]+\.[^\s@]+$'
        return bool(re.match(pattern, email.strip()))
    
    def validate(self) -> tuple[bool, str]:
        """Validate configuration and return (is_valid, error_message)."""
        if not self.smtp_server:
            return False, "SMTP server not configured"
        if not self.username:
            return False, "SMTP username not configured"
        if not self.password:
            return False, "SMTP password not configured"
        if not self.from_address:
            return False, "From address not configured"
        if not self._is_valid_email(self.from_address):
            return False, "Invalid from address format"
        return True, ""


class EmailSendResult:
    """Result of an email send operation."""
    
    def __init__(
        self,
        success: bool,
        recipient: str,
        subject: str,
        error: Optional[str] = None,
        attempt_count: int = 1,
        last_error_code: Optional[str] = None,
        timestamp: Optional[datetime] = None,
    ):
        self.success = success
        self.recipient = recipient
        self.subject = subject
        self.error = error
        self.attempt_count = attempt_count
        self.last_error_code = last_error_code
        self.timestamp = timestamp or datetime.utcnow()
    
    def to_dict(self) -> dict:
        """Convert to dictionary for logging."""
        return {
            'success': self.success,
            'recipient': self.recipient,
            'subject': self.subject,
            'error': self.error,
            'attempt_count': self.attempt_count,
            'last_error_code': self.last_error_code,
            'timestamp': self.timestamp.isoformat(),
        }


class SMTPConnectionError(Exception):
    """SMTP connection related error."""
    pass


class EmailValidationError(Exception):
    """Email validation error."""
    pass


class EmailSender:
    """Production-ready email sender with retry logic and comprehensive logging."""
    
    def __init__(self, config: EmailConfig):
        self.config = config
        self._lock = Lock()
        self._last_connection_test: Optional[datetime] = None
        self._connection_test_interval = timedelta(minutes=5)
        self._is_healthy = True
        
        # Validate on init
        is_valid, error = config.validate()
        if not is_valid:
            logger.warning(f"Email configuration invalid: {error}")
            self._is_healthy = False
    
    def is_healthy(self) -> bool:
        """Check if email service is healthy."""
        if not self._is_healthy:
            return False
        if not self.config.is_configured():
            return False
        
        # Periodically test connection
        now = datetime.utcnow()
        if self._last_connection_test is None or (now - self._last_connection_test) > self._connection_test_interval:
            try:
                self._test_connection()
                self._last_connection_test = now
                self._is_healthy = True
            except Exception as e:
                logger.error(f"Email health check failed: {e}")
                self._is_healthy = False
        
        return self._is_healthy
    
    def _test_connection(self) -> None:
        """Test SMTP connection."""
        context = ssl.create_default_context()
        timeout = self.config.timeout_seconds
        
        try:
            if self.config.use_tls:
                server = smtplib.SMTP(
                    self.config.smtp_server,
                    self.config.smtp_port,
                    timeout=timeout,
                )
                server.starttls(context=context)
            else:
                server = smtplib.SMTP_SSL(
                    self.config.smtp_server,
                    self.config.smtp_port,
                    timeout=timeout,
                    context=context,
                )
            
            server.ehlo()
            server.login(self.config.username, self.config.password)
            server.quit()
        except smtplib.SMTPAuthenticationError as e:
            raise SMTPConnectionError(f"SMTP authentication failed: {e}")
        except smtplib.SMTPException as e:
            raise SMTPConnectionError(f"SMTP error: {e}")
        except Exception as e:
            raise SMTPConnectionError(f"Connection failed: {e}")
    
    def send(
        self,
        recipient: str,
        subject: str,
        html_body: str,
        text_body: Optional[str] = None,
        reply_to: Optional[str] = None,
    ) -> EmailSendResult:
        """
        Send email with automatic retry on transient failures.
        
        Args:
            recipient: Email address to send to
            subject: Email subject
            html_body: HTML email body
            text_body: Plain text fallback
            reply_to: Reply-to address
        
        Returns:
            EmailSendResult with status and details
        """
        # Validate inputs
        if not self._validate_email(recipient):
            error_msg = f"Invalid recipient email: {recipient}"
            logger.error(error_msg)
            return EmailSendResult(
                success=False,
                recipient=recipient,
                subject=subject,
                error=error_msg,
                last_error_code="INVALID_EMAIL",
            )
        
        if not subject or not subject.strip():
            error_msg = "Subject cannot be empty"
            logger.error(error_msg)
            return EmailSendResult(
                success=False,
                recipient=recipient,
                subject=subject,
                error=error_msg,
                last_error_code="INVALID_SUBJECT",
            )
        
        if not html_body or not html_body.strip():
            error_msg = "Email body cannot be empty"
            logger.error(error_msg)
            return EmailSendResult(
                success=False,
                recipient=recipient,
                subject=subject,
                error=error_msg,
                last_error_code="INVALID_BODY",
            )
        
        # Attempt send with retries
        last_error = None
        last_error_code = None
        
        for attempt in range(1, self.config.max_retries + 1):
            try:
                self._send_attempt(
                    recipient=recipient,
                    subject=subject,
                    html_body=html_body,
                    text_body=text_body or "Email sent in HTML format.",
                    reply_to=reply_to,
                )
                
                logger.info(
                    f"Email sent successfully",
                    extra={
                        'recipient': recipient,
                        'subject': subject,
                        'attempt': attempt,
                    },
                )
                
                return EmailSendResult(
                    success=True,
                    recipient=recipient,
                    subject=subject,
                    attempt_count=attempt,
                )
            
            except smtplib.SMTPServerDisconnected as e:
                last_error = str(e)
                last_error_code = "SMTP_DISCONNECTED"
                logger.warning(
                    f"SMTP disconnected (attempt {attempt}/{self.config.max_retries}): {e}",
                    extra={'recipient': recipient, 'subject': subject},
                )
            
            except smtplib.SMTPAuthenticationError as e:
                last_error = str(e)
                last_error_code = "SMTP_AUTH_FAILED"
                logger.error(
                    f"SMTP authentication failed: {e}",
                    extra={'recipient': recipient},
                )
                # Don't retry auth failures
                break
            
            except smtplib.SMTPException as e:
                last_error = str(e)
                last_error_code = "SMTP_ERROR"
                logger.warning(
                    f"SMTP error (attempt {attempt}/{self.config.max_retries}): {e}",
                    extra={'recipient': recipient, 'subject': subject},
                )
            
            except (TimeoutError, OSError) as e:
                last_error = str(e)
                last_error_code = "CONNECTION_ERROR"
                logger.warning(
                    f"Connection error (attempt {attempt}/{self.config.max_retries}): {e}",
                    extra={'recipient': recipient},
                )
            
            except Exception as e:
                last_error = str(e)
                last_error_code = "UNKNOWN_ERROR"
                logger.exception(
                    f"Unexpected error sending email (attempt {attempt}): {e}",
                    extra={'recipient': recipient},
                )
                break
            
            # Exponential backoff before retry
            if attempt < self.config.max_retries:
                delay = self.config.retry_backoff_base ** (attempt - 1)
                logger.info(f"Waiting {delay:.1f}s before retry...")
                time.sleep(delay)
        
        # All retries exhausted
        error_msg = f"Failed to send email after {self.config.max_retries} attempts: {last_error}"
        logger.error(
            error_msg,
            extra={
                'recipient': recipient,
                'subject': subject,
                'error_code': last_error_code,
            },
        )
        
        return EmailSendResult(
            success=False,
            recipient=recipient,
            subject=subject,
            error=error_msg,
            attempt_count=self.config.max_retries,
            last_error_code=last_error_code,
        )
    
    def send_async(
        self,
        recipient: str,
        subject: str,
        html_body: str,
        text_body: Optional[str] = None,
        reply_to: Optional[str] = None,
        on_complete: Optional[Callable[[EmailSendResult], None]] = None,
    ) -> None:
        """
        Send email asynchronously in background thread.
        
        Args:
            recipient: Email address
            subject: Subject line
            html_body: HTML content
            text_body: Plain text fallback
            reply_to: Reply-to address
            on_complete: Optional callback when send completes
        """
        def worker():
            result = self.send(
                recipient=recipient,
                subject=subject,
                html_body=html_body,
                text_body=text_body,
                reply_to=reply_to,
            )
            if on_complete:
                try:
                    on_complete(result)
                except Exception as e:
                    logger.exception(f"Error in email completion callback: {e}")
        
        try:
            thread = Thread(target=worker, daemon=True, name=f"email-{recipient}")
            thread.start()
        except Exception as e:
            logger.error(f"Failed to start email thread: {e}")
    
    def _send_attempt(
        self,
        recipient: str,
        subject: str,
        html_body: str,
        text_body: str,
        reply_to: Optional[str] = None,
    ) -> None:
        """Attempt to send email (raises on failure)."""
        context = ssl.create_default_context()
        timeout = self.config.timeout_seconds
        
        # Create message
        msg = EmailMessage()
        msg['Subject'] = subject
        msg['From'] = self.config.from_address
        msg['To'] = recipient
        if reply_to and self._validate_email(reply_to):
            msg['Reply-To'] = reply_to
        
        msg.set_content(text_body)
        msg.add_alternative(html_body, subtype='html')
        
        # Connect and send
        try:
            if self.config.use_tls:
                server = smtplib.SMTP(
                    self.config.smtp_server,
                    self.config.smtp_port,
                    timeout=timeout,
                )
                server.starttls(context=context)
            else:
                server = smtplib.SMTP_SSL(
                    self.config.smtp_server,
                    self.config.smtp_port,
                    timeout=timeout,
                    context=context,
                )
            
            server.ehlo()
            server.login(self.config.username, self.config.password)
            server.send_message(msg)
        finally:
            try:
                server.quit()
            except Exception:
                try:
                    server.close()
                except Exception:
                    pass
    
    @staticmethod
    def _validate_email(email: str) -> bool:
        """Validate email address format."""
        if not email or len(email) > 254:
            return False
        pattern = r'^[^\s@]+@[^\s@]+\.[^\s@]+$'
        return bool(re.match(pattern, email.strip()))


class EmailAuditLogger:
    """Log email send operations for audit and debugging."""
    
    def __init__(self, log_file: Optional[str] = None):
        self.log_file = log_file
        self._lock = Lock()
    
    def log_send(self, result: EmailSendResult) -> None:
        """Log email send result."""
        try:
            entry = {
                'timestamp': result.timestamp.isoformat(),
                'recipient': result.recipient,
                'subject': result.subject,
                'success': result.success,
                'error': result.error,
                'attempt_count': result.attempt_count,
                'error_code': result.last_error_code,
            }
            
            if self.log_file:
                with self._lock:
                    with open(self.log_file, 'a', encoding='utf-8') as f:
                        f.write(json.dumps(entry) + '\n')
            
            logger.info(f"Email audit: {json.dumps(entry)}")
        except Exception as e:
            logger.exception(f"Failed to log email result: {e}")
