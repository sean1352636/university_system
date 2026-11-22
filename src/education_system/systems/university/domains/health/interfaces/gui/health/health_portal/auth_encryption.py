import logging

logger = logging.getLogger(__name__)

import os
import base64

from education_system import paths

try:
    from education_system.systems.university.infrastructure.security.audit_helpers import safe_log_security_event
    from education_system.systems.university.infrastructure.security.immutable_audit_log import AuditAction
    IMMUTABLE_AUDIT_AVAILABLE = True
except ImportError:
    IMMUTABLE_AUDIT_AVAILABLE = False

from education_system.systems.university.infrastructure.database.db import sqlite3


class _FallbackCipher:
    """Kept for old imports only. There is no fallback cipher any more: it
    was base64 with a prefix, which only looked encrypted. Sealing uses the
    managed key (``infrastructure/health/field_crypto``)."""

    def __new__(cls, *args, **kwargs):
        from education_system.systems.university.domains.health.infrastructure.health import (
            field_crypto,
        )
        return field_crypto.cipher()


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
        """The managed health field key (``var/secrets/health_field_key``).
        It used to sit as plain text beside the database."""
        from education_system.systems.university.domains.health.infrastructure.health import (
            field_crypto,
        )
        return field_crypto.key_bytes()

    def setup_logging(self):
        """Configure logging for audit trail"""
        log_dir = str(paths.UNIVERSITY_LOG_DIR)

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

                # required=True: an access to health data that can't be
                # audited raises instead of passing silently.
                safe_log_security_event(
                    required=True,
                    action=audit_action,
                    user_id=str(self.auth.current_user.get('id', '')),
                    resource_type=f'health_{resource_type}',
                    resource_id=str(resource_id) if resource_id else None,
                    details=details
                )

    def encrypt_sensitive_data(self, data):
        """Seal sensitive health data with the managed key."""
        from education_system.systems.university.domains.health.infrastructure.health import (
            field_crypto,
        )
        return None if data is None else field_crypto.seal(str(data))

    def decrypt_sensitive_data(self, encrypted_data):
        """Unseal a stored value. Values written before sealing pass through;
        the old base64 ``health-fallback:`` values are read once more so
        nothing stored that way is lost. A sealed value that cannot be
        decrypted raises instead of being shown garbled."""
        from education_system.systems.university.domains.health.infrastructure.health import (
            field_crypto,
        )
        if encrypted_data is None:
            return None
        if isinstance(encrypted_data, str) and encrypted_data.startswith(self._FALLBACK_PREFIX):
            payload = encrypted_data[len(self._FALLBACK_PREFIX):]
            return base64.urlsafe_b64decode(payload.encode()).decode()
        return field_crypto.unseal(encrypted_data)

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
        """Connect to the health repository, same as the health CLI does.

        This used to open student_records.db. Health tables exist in *both*
        databases, so the GUI was reading and writing its own copies while
        the CLI used the ones in health_records.db — the same portal showed
        different data depending on which interface you opened it from.

        Going through the pastoral health storage adapter puts both
        interfaces on one store, and that adapter attaches the student
        directory, so the queries here that join ``students`` still resolve.
        """
        try:
            from education_system.systems.university.domains.health.infrastructure.health.storage import (
                get_connection as health_get_connection,
            )
            return health_get_connection()
        except Exception:
            # Never fall back to health_records.db: it is the abandoned store,
            # and its foreign keys reference a `students` table it does not
            # have, so writes there fail outright. The university database is
            # where health data lives.
            from education_system import paths
            return sqlite3.connect(str(paths.UNIVERSITY_DEFAULT_DB_PATH))
