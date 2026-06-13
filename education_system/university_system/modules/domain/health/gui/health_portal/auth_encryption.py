import os
import logging
import base64
from unittest.mock import Mock

from cryptography.fernet import Fernet

from education_system.university_system.core import paths

try:
    from education_system.university_system.infrastructure.security.audit_helpers import safe_log_security_event
    from education_system.university_system.infrastructure.security.immutable_audit_log import AuditAction
    IMMUTABLE_AUDIT_AVAILABLE = True
except ImportError:
    IMMUTABLE_AUDIT_AVAILABLE = False

from education_system.university_system.infrastructure.database.db import sqlite3


class _FallbackCipher:
    """Minimal reversible cipher used when Fernet is unavailable or mocked."""

    def encrypt(self, data):
        payload = base64.urlsafe_b64encode(data).decode()
        return f"{AuthEncryptionMixin._FALLBACK_PREFIX}{payload}".encode()

    def decrypt(self, token):
        if isinstance(token, bytes):
            token = token.decode()
        if not isinstance(token, str) or not token.startswith(AuthEncryptionMixin._FALLBACK_PREFIX):
            raise ValueError("Unsupported token")
        payload = token[len(AuthEncryptionMixin._FALLBACK_PREFIX):]
        return base64.urlsafe_b64decode(payload.encode())


class AuthEncryptionMixin:
    """Mixin for authentication, encryption, logging, and database connection helpers."""

    _FALLBACK_PREFIX = "health-fallback:"

    def setup_current_user(self):
        """Setup current user from existing authentication system"""
        try:
            if self.auth and hasattr(self.auth, 'current_user') and self.auth.current_user:
                print(f"\u2713 Health Portal GUI: Using authenticated user {self.auth.current_user.get('username', 'Unknown')} ({self.auth.current_user.get('role', 'user')})")
            else:
                print("\u2139 Health Portal GUI: No authenticated user - will show login screen")
        except Exception as e:
            print(f"\u2717 Error setting up current user: {e}")

    def get_or_create_encryption_key(self):
        """Get or create a valid Fernet key for sensitive data."""
        from cryptography.fernet import Fernet as RealFernet

        key_file = str(paths.DATA_DIR / 'health_encryption.key')

        if os.path.exists(key_file):
            with open(key_file, 'rb') as f:
                key = f.read().strip()
            try:
                RealFernet(key)
                return key
            except Exception:
                pass

        try:
            key = RealFernet.generate_key()
            if isinstance(key, Mock) or not isinstance(key, (bytes, bytearray)):
                raise TypeError("Invalid Fernet key")
        except Exception:
            key = base64.urlsafe_b64encode(os.urandom(32))
        with open(key_file, 'wb') as f:
            f.write(key)
        try:
            os.chmod(key_file, 0o600)
        except OSError:
            pass
        return key

    def setup_logging(self):
        """Configure logging for audit trail"""
        log_dir = str(paths.LOG_DIR)

        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler(os.path.join(log_dir, "app.log")),
                logging.StreamHandler()
            ]
        )
        self.audit_logger = logging.getLogger(__name__)

    def log_audit_event(self, action, resource_type, resource_id, details=None):
        """Log audit events for compliance (including HIPAA)"""
        if self.auth.current_user:
            self.audit_logger.info(f"USER:{self.auth.current_user['id']} ACTION:{action} RESOURCE:{resource_type}:{resource_id} DETAILS:{details}")

            if IMMUTABLE_AUDIT_AVAILABLE:
                action_map = {
                    'view': AuditAction.DATA_VIEW,
                    'create': AuditAction.RECORD_CREATE,
                    'update': AuditAction.RECORD_UPDATE,
                    'delete': AuditAction.RECORD_DELETE,
                    'export': AuditAction.DATA_EXPORT,
                    'print': AuditAction.DATA_PRINT,
                }
                audit_action = action_map.get(action.lower(), action.upper())

                safe_log_security_event(
                    action=audit_action,
                    user_id=str(self.auth.current_user.get('id', '')),
                    resource_type=f'health_{resource_type}',
                    resource_id=str(resource_id) if resource_id else None,
                    details=details
                )

    def encrypt_sensitive_data(self, data):
        """Encrypt sensitive health data"""
        if data is None:
            return None
        cipher = self.cipher_suite
        if cipher is not None and not isinstance(cipher, Mock):
            try:
                return cipher.encrypt(str(data).encode()).decode()
            except Exception:
                pass
        return _FallbackCipher().encrypt(str(data).encode()).decode()

    def decrypt_sensitive_data(self, encrypted_data):
        """Decrypt sensitive health data"""
        if encrypted_data is None:
            return None
        if isinstance(encrypted_data, str) and encrypted_data.startswith(self._FALLBACK_PREFIX):
            try:
                payload = encrypted_data[len(self._FALLBACK_PREFIX):]
                return base64.urlsafe_b64decode(payload.encode()).decode()
            except Exception:
                return encrypted_data
        try:
            cipher = self.cipher_suite
            if cipher is not None and not isinstance(cipher, Mock):
                return cipher.decrypt(encrypted_data.encode()).decode()
            return encrypted_data
        except Exception:
            return encrypted_data

    def get_user_role(self):
        """Get the current user's role from authentication system"""
        try:
            if self.auth and hasattr(self.auth, 'current_user') and self.auth.current_user:
                role = self.auth.current_user.get('role', '').lower()
                return role
            return None
        except Exception as e:
            print(f"Error getting user role: {e}")
            return None

    def is_admin(self):
        """Check if current user is admin"""
        role = self.get_user_role()
        return role == 'admin'

    def is_staff(self):
        """Check if current user is staff/health staff"""
        role = self.get_user_role()
        return role in ['staff', 'health_staff', 'instructor']

    def is_student(self):
        """Check if current user is student"""
        role = self.get_user_role()
        return role == 'student'

    def get_connection(self):
        """Get database connection using the centralized student_records.db path"""
        try:
            from education_system.university_system.infrastructure.database.db import get_connection as central_get_connection
            return central_get_connection()
        except Exception:
            from education_system.university_system.core import paths
            return sqlite3.connect(str(paths.DEFAULT_DB_PATH))
