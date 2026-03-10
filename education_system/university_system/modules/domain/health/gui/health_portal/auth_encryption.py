import os
import logging

from cryptography.fernet import Fernet

from education_system.university_system.modules.shared.constants import paths

try:
    from education_system.university_system.infrastructure.security.audit_helpers import safe_log_security_event
    from education_system.university_system.infrastructure.security.immutable_audit_log import AuditAction
    IMMUTABLE_AUDIT_AVAILABLE = True
except ImportError:
    IMMUTABLE_AUDIT_AVAILABLE = False

from education_system.university_system.infrastructure.database.db import sqlite3


class AuthEncryptionMixin:
    """Mixin for authentication, encryption, logging, and database connection helpers."""

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
        key_file = str(paths.DATA_DIR / 'health_encryption.key')

        if os.path.exists(key_file):
            with open(key_file, 'rb') as f:
                key = f.read().strip()
            try:
                Fernet(key)
                return key
            except Exception:
                pass

        key = Fernet.generate_key()
        with open(key_file, 'wb') as f:
            f.write(key)
        return key

    def setup_logging(self):
        """Configure logging for audit trail"""
        log_dir = str(paths.LOG_DIR)

        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler(os.path.join(log_dir, "health_portal_audit.log")),
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
        return self.cipher_suite.encrypt(str(data).encode()).decode()

    def decrypt_sensitive_data(self, encrypted_data):
        """Decrypt sensitive health data"""
        if encrypted_data is None:
            return None
        try:
            return self.cipher_suite.decrypt(encrypted_data.encode()).decode()
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
            from education_system.university_system.modules.shared.constants import paths
            return sqlite3.connect(str(paths.DEFAULT_DB_PATH))
