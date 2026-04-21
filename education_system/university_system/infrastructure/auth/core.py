"""
Core Authentication Module - UserAuth Class

This is the CRITICAL orchestration layer that assembles all authentication components.
It provides the main UserAuth class that delegates to specialized managers for different
authentication concerns while maintaining 100% backward compatibility with the original API.

Architecture:
    UserAuth (this file)
        ├── DatabaseConnectionManager (database operations)
        ├── PasswordManager (password hashing/validation)
        ├── LoginManager (login/logout logic)
        ├── SessionManager (session tracking)
        ├── UserManager (user CRUD operations)
        ├── PermissionManager (permission checks)
        ├── RoleManager (role management)
        ├── MFAManager (multi-factor authentication)
        └── AccountSecurityManager (security features)

The UserAuth class serves as the primary interface for all authentication operations,
delegating to appropriate managers while maintaining state and session information.
"""

from typing import Optional, Dict, List, Any, Union, Tuple
import json
import traceback
import logging
from education_system.university_system.infrastructure.database.db import sqlite3, DatabaseManager
import hashlib
import secrets
import re
import os
import time
from datetime import datetime, timedelta
import pyotp
import qrcode
import io
import base64
import contextlib
import threading
from pathlib import Path
from education_system.university_system.infrastructure.database.db import get_connection
import sys

# Import constants and paths
from education_system.university_system.core import paths
from education_system.university_system.core import defaults
from education_system.university_system.core.sql_safety import (
    validate_column_definition,
    SQLIdentifierError,
)

# Import custom exceptions
from education_system.university_system.infrastructure.exceptions import (
    AuthenticationError,
    InvalidCredentialsError,
    SessionExpiredError,
    PermissionDeniedError,
    MFARequiredError,
    ValidationError,
    InvalidInputError,
    DatabaseError,
)

# Initialize logger
logger = logging.getLogger(__name__)

# Import i18n
from education_system.university_system.core.i18n import get_text, _

# Import centralized activity logger
try:
    from education_system.university_system.core.activity_logger import (
        set_user, log_login, log_logout, log_activity, log_access
    )
    ACTIVITY_LOGGER_AVAILABLE = True
except ImportError:
    ACTIVITY_LOGGER_AVAILABLE = False

# Import immutable audit logging for compliance
try:
    from education_system.university_system.infrastructure.security.audit_helpers import safe_log_security_event
    from education_system.university_system.infrastructure.security.immutable_audit_log import AuditAction
    IMMUTABLE_AUDIT_AVAILABLE = True
except ImportError:
    IMMUTABLE_AUDIT_AVAILABLE = False

# Import security alerting for real-time notifications
try:
    from education_system.university_system.infrastructure.security.security_alerts import (
        alert_account_lockout,
    )
    SECURITY_ALERTS_AVAILABLE = True
except ImportError:
    SECURITY_ALERTS_AVAILABLE = False

# Import MFA enforcement
try:
    from education_system.university_system.infrastructure.auth.mfa_enforcement import (
        enforce_mfa_on_login,
    )
    MFA_ENFORCEMENT_AVAILABLE = True
except ImportError:
    MFA_ENFORCEMENT_AVAILABLE = False

# Import optional dependencies with proper dependency injection
from education_system.university_system.infrastructure.auth.optional_dependencies import (
    get_chatbot,
    get_chatbot_class,
    get_voice_interface,
    is_chatbot_available,
    is_voice_interface_available,
    OptionalDependencyError,
    ChatbotInterface,
    VoiceInterface,
)

# Check availability of optional features
CHATBOT_AVAILABLE = is_chatbot_available()
VOICE_AVAILABLE = is_voice_interface_available()

# Import UniversityChatbot class if available
UniversityChatbot = None
if CHATBOT_AVAILABLE:
    try:
        UniversityChatbot = get_chatbot_class()
        logger.info("Chatbot module is available")
    except (ImportError, OptionalDependencyError, AttributeError) as e:
        logger.warning(f"Failed to get chatbot class: {e}")
        CHATBOT_AVAILABLE = False
else:
    logger.info("Chatbot module not available - feature will be disabled")

# Import constants (safe to import at module level)
from education_system.university_system.infrastructure.auth.core_utils.constants import ROLES, PERMISSIONS

# Manager imports moved to __init__ to avoid circular dependencies

# Global variable to store the current auth instance with thread-safe access
_current_auth_instance = None
_auth_instance_lock = threading.Lock()


def get_current_user():
    """
    Get the current logged-in user information from the global auth instance.

    Returns
    -------
    dict or None
        User information dictionary containing user details if a user
        is logged in, or None if no user is logged in.
    """
    with _auth_instance_lock:
        if _current_auth_instance and _current_auth_instance.current_user:
            return _current_auth_instance.current_user
        return None


def set_auth_instance(auth_instance):
    """
    Set the global authentication instance for the application.

    Parameters
    ----------
    auth_instance : UserAuth
        The authentication instance to register globally.
    """
    global _current_auth_instance
    with _auth_instance_lock:
        _current_auth_instance = auth_instance


def get_auth_instance():
    """Get the current global auth instance"""
    with _auth_instance_lock:
        return _current_auth_instance


class MinimalVoiceInterface:
    """Minimal fallback voice interface when full chatbot is unavailable"""
    def __init__(self):
        self.enabled = False

    def initialize(self):
        pass

    def process_voice_input(self, *args, **kwargs):
        return None

    def text_to_speech(self, *args, **kwargs):
        pass


class UserAuth:
    """
    Central authentication and authorization system.

    This class orchestrates all authentication operations by delegating to
    specialized manager classes while maintaining backward compatibility with
    the original monolithic interface.

    Attributes:
        current_user (dict): Currently logged-in user information
        last_activity (datetime): Timestamp of last user activity
        session_timeout (int): Session timeout in minutes
        db_manager (DatabaseConnectionManager): Database connection manager
        password_manager (PasswordManager): Password operations
        login_manager (LoginManager): Login/logout operations
        session_manager (SessionManager): Session management
        user_manager (UserManager): User CRUD operations
        permission_manager (PermissionManager): Permission checks
        role_manager (RoleManager): Role management
        mfa_manager (MFAManager): Multi-factor authentication
        account_security_manager (AccountSecurityManager): Security features
    """

    # Class-level lock for thread-safe initialization
    _init_lock = threading.Lock()
    _db_initialized = False

    # Re-export as a static method so tests can patch UserAuth.log_activity_with_connection
    from education_system.university_system.infrastructure.auth.managers.activity_logger import (
        log_activity_with_connection,
    )
    log_activity_with_connection = staticmethod(log_activity_with_connection)

    def __init__(self, db_path=None, config_path=None):
        """
        Initialize UserAuth with proper attribute initialization.

        Parameters:
            db_path (str, optional): Path to database file
            config_path (str, optional): Path to configuration file
        """
        try:
            # CRITICAL: Initialize these attributes FIRST
            self.current_user = None
            self.last_activity = None
            self.session_timeout = 30  # minutes
            self.login_attempts = {}
            self.max_attempts = 5
            self.lockout_time = 15  # minutes

            # Core initialization with path normalization
            def _normalise_path(value, default_path: Path) -> str:
                """Resolve path to absolute path rooted in the project."""
                if value is None:
                    return os.fspath(default_path)

                candidate = Path(value)
                if candidate.is_absolute():
                    return os.fspath(candidate)

                return os.fspath(default_path.parent / candidate)

            self.db_path = _normalise_path(db_path, paths.DEFAULT_DB_PATH)
            self.config_path = _normalise_path(config_path, paths.CHATBOT_CONFIG_PATH)
            self.log_dir = os.fspath(paths.LOG_DIR)
            self.upload_dir = os.fspath(paths.CHATBOT_UPLOAD_DIR)
            self.models_dir = os.fspath(paths.CHATBOT_MODELS_DIR)

            # Authentication system integration
            self.auth_system = None
            self.authenticated_sessions = {}
            self.conversation_contexts = {}

            # Import managers here to avoid circular dependencies
            from education_system.university_system.infrastructure.auth.managers.database_manager import DatabaseConnectionManager
            from education_system.university_system.infrastructure.auth.managers import password_manager
            from education_system.university_system.infrastructure.auth.managers.session_manager import SessionManager
            from education_system.university_system.infrastructure.auth.managers.user_manager import UserManager
            from education_system.university_system.infrastructure.auth.managers.permission_manager import PermissionManager
            from education_system.university_system.infrastructure.auth.managers.role_manager import RoleManager
            from education_system.university_system.infrastructure.auth.managers.mfa_manager import MFAManager
            from education_system.university_system.infrastructure.auth.managers.account_security import AccountSecurityManager
            from education_system.university_system.infrastructure.auth.managers.login_manager import LoginManager
            from education_system.university_system.infrastructure.auth.managers.account_linking_manager import AccountLinkingManager
            from education_system.university_system.infrastructure.auth.managers.sso_manager import SSOManager
            from education_system.university_system.infrastructure.auth.managers.webauthn_manager import WebAuthnManager
            from education_system.university_system.infrastructure.auth.managers.biometric_manager import BiometricManager
            from education_system.university_system.infrastructure.auth.managers.delegated_access_manager import DelegatedAccessManager

            # Initialize database manager
            self.db_manager = DatabaseConnectionManager(self.db_path)

            # Load configuration FIRST
            self.config = self.load_config()

            # Initialize directories
            self.ensure_directories()

            # Initialize voice interface with error handling
            try:
                if CHATBOT_AVAILABLE:
                    # Try to import the real VoiceInterface
                    from education_system.university_system.infrastructure.ai.university_chatbot import VoiceInterface
                    self.voice_interface = VoiceInterface()
                    if hasattr(self.voice_interface, 'initialize'):
                        self.voice_interface.initialize()
                else:
                    self.voice_interface = MinimalVoiceInterface()
            except (ImportError, NameError, AttributeError):
                # Fallback to minimal implementation
                self.voice_interface = MinimalVoiceInterface()
                logger.info("Using minimal voice interface - voice features disabled")

            # Additional chatbot attributes
            self.nlp = None
            self.intent_classifier = None
            self.sentiment_analyzer = None
            self.qa_pipeline = None
            self.vectorizer = None
            self.intents = {}
            self.faq_database = {}

            # Conversation tracking
            self.conversation_history = {}

            # Initialize LoginManager with all required dependencies
            # Use local imports to avoid circular dependencies
            from education_system.university_system.infrastructure.auth.managers import activity_logger

            def activity_logger_wrapper(username, action, details=None, user_id=None):
                """Wrapper for activity_logger that binds db_path"""
                return activity_logger.log_activity(self.db_path, username, action, details, user_id)

            # Import validators for UserManager
            from education_system.university_system.infrastructure.auth.core_utils.utils import (
                validate_username, validate_password, validate_email
            )

            # Initialize specialized managers in correct dependency order
            self.password_manager = password_manager  # Function-based module
            self.session_manager = SessionManager(
                self.db_manager, activity_logger_wrapper, self.session_timeout
            )
            self.permission_manager = PermissionManager(
                self.db_manager,
                activity_logger_wrapper,
                lambda: self.current_user,
                lambda: self.current_user is not None,
            )
            self.role_manager = RoleManager(
                self.db_manager,
                activity_logger_wrapper,
                lambda: self.current_user,
            )
            self.mfa_manager = MFAManager(self.db_manager, activity_logger_wrapper)
            self.account_security_manager = AccountSecurityManager(
                self.db_manager, activity_logger_wrapper
            )
            self.user_manager = UserManager(
                self.db_manager,
                activity_logger_wrapper,
                self.password_manager.hash_password,
                validate_username,
                validate_password,
                validate_email,
                lambda: self.current_user,
            )

            # Simple helper functions to avoid circular imports
            def simple_role_inferrer(username):
                """Infer role from username pattern"""
                username_lower = username.lower()
                if 'admin' in username_lower:
                    return 'admin'
                elif 'staff' in username_lower:
                    return 'staff'
                elif 'instructor' in username_lower or 'teacher' in username_lower:
                    return 'instructor'
                elif 'parent' in username_lower:
                    return 'parent'
                return 'student'

            def simple_name_deriver(username):
                """Derive name from username"""
                import re
                tokens = [t for t in re.split(r'[._\-\s]+', username) if t]
                if len(tokens) >= 2:
                    return tokens[0].title(), tokens[-1].title()
                if tokens:
                    return tokens[0].title(), 'User'
                return 'User', 'Account'

            self.login_manager = LoginManager(
                db_manager=self.db_manager,
                activity_logger=activity_logger_wrapper,
                password_hasher=self.password_manager.hash_password,
                account_security=self.account_security_manager,
                mfa_manager=self.mfa_manager,
                permission_getter=self.permission_manager.get_user_permissions,
                session_manager=self.session_manager,
                role_inferrer=simple_role_inferrer,
                name_deriver=simple_name_deriver
            )

            # Initialize extended authentication managers
            self.account_linking_manager = AccountLinkingManager(
                self.db_manager,
                activity_logger_wrapper,
                lambda: self.current_user,
                self.permission_manager,
            )
            self.sso_manager = SSOManager(
                self.db_manager,
                activity_logger_wrapper,
                lambda: self.current_user,
            )
            self.webauthn_manager = WebAuthnManager(
                self.db_manager,
                activity_logger_wrapper,
                lambda: self.current_user,
            )
            self.biometric_manager = BiometricManager(
                self.db_manager,
                activity_logger_wrapper,
                lambda: self.current_user,
            )
            self.delegated_access_manager = DelegatedAccessManager(
                self.db_manager,
                activity_logger_wrapper,
                lambda: self.current_user,
                self.permission_manager,
            )

            # Initialize the database
            self._init_db()

            # ── Shared auth integration ──────────────────────────────
            # Initialise the shared auth database and create a shared
            # UserAuth instance for credential verification. This lets
            # all four systems (university, college, school, primary)
            # share one auth database and one login flow.
            try:
                from education_system.shared.auth.schema import (
                    initialise_auth_db as _init_shared_db,
                    seed_default_users as _seed_shared,
                )
                from education_system.shared.auth.core import (
                    UserAuth as SharedUserAuth,
                )
                _init_shared_db()
                _seed_shared()
                self._shared_auth = SharedUserAuth()
            except Exception as exc:
                logger.warning("Could not initialise shared auth: %s", exc)
                self._shared_auth = None

            # Set global auth instance
            set_auth_instance(self)

            logger.info("UserAuth initialized successfully!")

        except sqlite3.Error as e:
            logger.critical(f"Database error in UserAuth initialization: {e}")
            self._set_safe_defaults(db_path)
        except (OSError, IOError) as e:
            logger.critical(f"File system error in UserAuth initialization: {e}")
            self._set_safe_defaults(db_path)
        except (ValueError, TypeError, KeyError) as e:
            logger.critical(f"Configuration error in UserAuth initialization: {e}")
            self._set_safe_defaults(db_path)

    def _set_safe_defaults(self, db_path):
        """Set minimal safe defaults after initialization failure"""
        self._shared_auth = None
        self.current_user = None
        self.last_activity = None
        self.session_timeout = 30
        self.login_attempts = {}
        self.max_attempts = 5
        self.lockout_time = 15
        self.config = {}
        self.conversation_history = {}
        self.auth_system = None
        # Preserve the already-normalized db_path if available, otherwise normalize now
        if not hasattr(self, 'db_path') or self.db_path is None:
            self.db_path = os.fspath(paths.DEFAULT_DB_PATH) if db_path is None else db_path

        # Still try to initialize database and managers
        try:
            # Import managers here to avoid circular dependencies
            from education_system.university_system.infrastructure.auth.managers.database_manager import DatabaseConnectionManager
            from education_system.university_system.infrastructure.auth.managers import password_manager
            from education_system.university_system.infrastructure.auth.managers.session_manager import SessionManager
            from education_system.university_system.infrastructure.auth.managers.user_manager import UserManager
            from education_system.university_system.infrastructure.auth.managers.permission_manager import PermissionManager
            from education_system.university_system.infrastructure.auth.managers.role_manager import RoleManager
            from education_system.university_system.infrastructure.auth.managers.mfa_manager import MFAManager
            from education_system.university_system.infrastructure.auth.managers.account_security import AccountSecurityManager
            from education_system.university_system.infrastructure.auth.managers.login_manager import LoginManager
            from education_system.university_system.infrastructure.auth.managers.account_linking_manager import AccountLinkingManager
            from education_system.university_system.infrastructure.auth.managers.sso_manager import SSOManager
            from education_system.university_system.infrastructure.auth.managers.webauthn_manager import WebAuthnManager
            from education_system.university_system.infrastructure.auth.managers.biometric_manager import BiometricManager
            from education_system.university_system.infrastructure.auth.managers.delegated_access_manager import DelegatedAccessManager
            from education_system.university_system.infrastructure.auth.managers import activity_logger
            from education_system.university_system.infrastructure.auth.core_utils.utils import (
                validate_username, validate_password, validate_email
            )

            self.db_manager = DatabaseConnectionManager(self.db_path)

            def activity_logger_wrapper(username, action, details=None, user_id=None):
                """Wrapper for activity_logger that binds db_path"""
                return activity_logger.log_activity(self.db_path, username, action, details, user_id)

            # Initialize all managers in correct dependency order
            self.password_manager = password_manager  # Function-based module
            self.session_manager = SessionManager(
                self.db_manager, activity_logger_wrapper, self.session_timeout
            )
            self.permission_manager = PermissionManager(
                self.db_manager,
                activity_logger_wrapper,
                lambda: self.current_user,
                lambda: self.current_user is not None,
            )
            self.role_manager = RoleManager(
                self.db_manager,
                activity_logger_wrapper,
                lambda: self.current_user,
            )
            self.mfa_manager = MFAManager(self.db_manager, activity_logger_wrapper)
            self.account_security_manager = AccountSecurityManager(
                self.db_manager, activity_logger_wrapper
            )
            self.user_manager = UserManager(
                self.db_manager,
                activity_logger_wrapper,
                self.password_manager.hash_password,
                validate_username,
                validate_password,
                validate_email,
                lambda: self.current_user,
            )

            # Simple helper functions to avoid circular imports
            def simple_role_inferrer(username):
                """Infer role from username pattern"""
                username_lower = username.lower()
                if 'admin' in username_lower:
                    return 'admin'
                elif 'staff' in username_lower:
                    return 'staff'
                elif 'instructor' in username_lower or 'teacher' in username_lower:
                    return 'instructor'
                elif 'parent' in username_lower:
                    return 'parent'
                return 'student'

            def simple_name_deriver(username):
                """Derive name from username"""
                import re
                tokens = [t for t in re.split(r'[._\-\s]+', username) if t]
                if len(tokens) >= 2:
                    return tokens[0].title(), tokens[-1].title()
                if tokens:
                    return tokens[0].title(), 'User'
                return 'User', 'Account'

            self.login_manager = LoginManager(
                db_manager=self.db_manager,
                activity_logger=activity_logger_wrapper,
                password_hasher=self.password_manager.hash_password,
                account_security=self.account_security_manager,
                mfa_manager=self.mfa_manager,
                permission_getter=self.permission_manager.get_user_permissions,
                session_manager=self.session_manager,
                role_inferrer=simple_role_inferrer,
                name_deriver=simple_name_deriver
            )

            # Initialize extended authentication managers
            self.account_linking_manager = AccountLinkingManager(
                self.db_manager,
                activity_logger_wrapper,
                lambda: self.current_user,
                self.permission_manager,
            )
            self.sso_manager = SSOManager(
                self.db_manager,
                activity_logger_wrapper,
                lambda: self.current_user,
            )
            self.webauthn_manager = WebAuthnManager(
                self.db_manager,
                activity_logger_wrapper,
                lambda: self.current_user,
            )
            self.biometric_manager = BiometricManager(
                self.db_manager,
                activity_logger_wrapper,
                lambda: self.current_user,
            )
            self.delegated_access_manager = DelegatedAccessManager(
                self.db_manager,
                activity_logger_wrapper,
                lambda: self.current_user,
                self.permission_manager,
            )

            self._init_db()
        except sqlite3.Error as db_error:
            logger.error(f"Database initialization also failed: {db_error}")
        except Exception as e:
            logger.error(f"Manager initialization failed: {e}")

    # ==========================================================================
    # DATABASE INITIALIZATION
    # ==========================================================================

    def _init_db(self):
        """
        Initialize database tables needed for authentication.

        Thread-safe: Uses double-checked locking pattern to prevent
        race conditions during initialization.
        """
        # Fast path - check without lock first
        if UserAuth._db_initialized:
            return

        # Slow path - acquire lock and double-check
        with UserAuth._init_lock:
            # Double-check after acquiring lock
            if UserAuth._db_initialized:
                return

            # All initialization happens within the lock
            self._do_init_db()
            UserAuth._db_initialized = True

    def _do_init_db(self):
        """Perform the actual database initialization (called within lock)."""
        conn = sqlite3.connect(self.db_path)
        try:
            cursor = conn.cursor()

            # Ensure the student catalogue exists before creating dependent tables
            self._ensure_students_table(cursor)

            # Create users table for storing user profile information
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                first_name TEXT NOT NULL,
                last_name TEXT NOT NULL,
                email TEXT UNIQUE NOT NULL,
                role TEXT NOT NULL,
                student_id TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                FOREIGN KEY (student_id) REFERENCES students (student_id)
            )
            ''')

            # Create user_accounts table - for storing authentication data
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS user_accounts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                salt TEXT NOT NULL,
                user_id INTEGER NOT NULL,
                is_active INTEGER DEFAULT 1,
                last_login TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                password_reset_required INTEGER DEFAULT 0,
                two_fa_enabled INTEGER DEFAULT 0,
                two_fa_secret TEXT,
                FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE
            )
            ''')

            # Create two_fa_recovery_codes table
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS two_fa_recovery_codes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                code_hash TEXT NOT NULL,
                is_used INTEGER DEFAULT 0,
                created_at TEXT NOT NULL,
                used_at TEXT,
                FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE
            )
            ''')

            # Create roles table
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS roles (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                role_name TEXT UNIQUE NOT NULL,
                description TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            ''')

            # Create permissions table
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS permissions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                permission_name TEXT UNIQUE NOT NULL,
                description TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
            ''')

            # Create role_permissions table
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS role_permissions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                role_id INTEGER NOT NULL,
                permission_id INTEGER NOT NULL,
                FOREIGN KEY (role_id) REFERENCES roles (id),
                FOREIGN KEY (permission_id) REFERENCES permissions (id),
                UNIQUE(role_id, permission_id)
            )
            ''')

            # Create user_permissions table
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS user_permissions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                permission_id INTEGER NOT NULL,
                granted INTEGER NOT NULL,
                UNIQUE(user_id, permission_id),
                FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE,
                FOREIGN KEY(permission_id) REFERENCES permissions(id) ON DELETE CASCADE
            )
            ''')

            # Create login_attempts table
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS login_attempts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT NOT NULL,
                attempt_time TEXT NOT NULL,
                ip_address TEXT,
                success INTEGER NOT NULL
            )
            ''')

            # Create activity_log table
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS activity_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                username TEXT NOT NULL,
                action TEXT NOT NULL,
                details TEXT,
                timestamp TEXT NOT NULL,
                ip_address TEXT,
                FOREIGN KEY (user_id) REFERENCES users (id)
            )
            ''')

            conn.commit()

            # Initialize roles if they don't exist
            cursor.execute('SELECT COUNT(*) FROM roles')
            role_count = cursor.fetchone()[0]

            if role_count == 0:
                timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

                # Insert default roles
                for role_name, description in ROLES.items():
                    cursor.execute(
                        'INSERT INTO roles (role_name, description, created_at, updated_at) VALUES (?, ?, ?, ?)',
                        (role_name, description, timestamp, timestamp)
                    )

                conn.commit()

            # Initialize permissions if they don't exist
            cursor.execute('SELECT COUNT(*) FROM permissions')
            permission_count = cursor.fetchone()[0]

            if permission_count == 0:
                timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

                # Gather all unique permissions
                all_permissions = set()
                for perms in PERMISSIONS.values():
                    all_permissions.update(perms)

                # Insert permissions
                for perm in all_permissions:
                    description = ' '.join(word.capitalize() for word in perm.split('_'))
                    cursor.execute(
                        'INSERT INTO permissions (permission_name, description, created_at) VALUES (?, ?, ?)',
                        (perm, description, timestamp)
                    )

                conn.commit()

                # Now associate permissions with roles
                for role, perms in PERMISSIONS.items():
                    cursor.execute('SELECT id FROM roles WHERE role_name = ?', (role,))
                    role_result = cursor.fetchone()
                    if role_result:
                        role_id = role_result[0]

                        for perm in perms:
                            cursor.execute('SELECT id FROM permissions WHERE permission_name = ?', (perm,))
                            perm_result = cursor.fetchone()
                            if perm_result:
                                perm_id = perm_result[0]

                                cursor.execute(
                                    'SELECT COUNT(*) FROM role_permissions WHERE role_id = ? AND permission_id = ?',
                                    (role_id, perm_id)
                                )
                                if cursor.fetchone()[0] == 0:
                                    cursor.execute(
                                        'INSERT INTO role_permissions (role_id, permission_id) VALUES (?, ?)',
                                        (role_id, perm_id)
                                    )

                conn.commit()
            else:
                # If permissions already exist, ensure all permissions in PERMISSIONS are created
                timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

                all_permissions = set()
                for perms in PERMISSIONS.values():
                    all_permissions.update(perms)

                for perm in all_permissions:
                    cursor.execute('SELECT COUNT(*) FROM permissions WHERE permission_name = ?', (perm,))
                    if cursor.fetchone()[0] == 0:
                        description = ' '.join(word.capitalize() for word in perm.split('_'))
                        cursor.execute(
                            'INSERT INTO permissions (permission_name, description, created_at) VALUES (?, ?, ?)',
                            (perm, description, timestamp)
                        )

                conn.commit()

                # Then ensure all role-permission associations exist
                for role, perms in PERMISSIONS.items():
                    cursor.execute('SELECT id FROM roles WHERE role_name = ?', (role,))
                    role_result = cursor.fetchone()
                    if role_result:
                        role_id = role_result[0]

                        for perm in perms:
                            cursor.execute('SELECT id FROM permissions WHERE permission_name = ?', (perm,))
                            perm_result = cursor.fetchone()
                            if perm_result:
                                perm_id = perm_result[0]

                                cursor.execute(
                                    'SELECT COUNT(*) FROM role_permissions WHERE role_id = ? AND permission_id = ?',
                                    (role_id, perm_id)
                                )
                                if cursor.fetchone()[0] == 0:
                                    cursor.execute(
                                        'INSERT INTO role_permissions (role_id, permission_id) VALUES (?, ?)',
                                        (role_id, perm_id)
                                    )

                conn.commit()

            # Create default student record if needed
            self._create_default_student_if_needed(cursor, conn)

            # Create default accounts ONLY if they don't exist
            self._create_default_accounts_if_needed(cursor, conn)
        finally:
            # Always close the connection, even if an error occurs
            conn.close()

    def _ensure_students_table(self, cursor):
        """Guarantee the student catalogue exists for auth relationships"""
        try:
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS students (
                student_id TEXT PRIMARY KEY,
                email_address TEXT,
                title TEXT,
                first_name TEXT,
                middle_name TEXT,
                last_name TEXT,
                gender TEXT,
                dob TEXT,
                age INTEGER,
                course TEXT,
                registration_datetime TEXT,
                status TEXT DEFAULT 'Active',
                enrollment_date TEXT
            )
            ''')

            cursor.execute("PRAGMA table_info(students)")
            existing_columns = {column[1] for column in cursor.fetchall()}

            required_columns = {
                'email_address': 'TEXT',
                'title': 'TEXT',
                'first_name': 'TEXT',
                'middle_name': 'TEXT',
                'last_name': 'TEXT',
                'gender': 'TEXT',
                'dob': 'TEXT',
                'age': 'INTEGER',
                'course': 'TEXT',
                'registration_datetime': 'TEXT',
                'status': 'TEXT DEFAULT "Active"',
                'enrollment_date': 'TEXT'
            }

            # Use centralized SQL safety validation for column definitions
            for column, definition in required_columns.items():
                if column not in existing_columns:
                    try:
                        # Validate column definition using SQL safety module
                        col_def = validate_column_definition(column, definition)
                        cursor.execute('ALTER TABLE students ADD COLUMN [' + col_def.name + '] ' + col_def.type_def)
                        logging.info(f"Added missing column '{column}' to students table")
                    except SQLIdentifierError as e:
                        logging.warning(f"Invalid column definition for '{column}': {e}")
                        continue
                    except sqlite3.OperationalError as e:
                        if "duplicate column name" in str(e).lower():
                            continue
                        logging.warning(f"Could not add column '{column}' to students table: {e}")
                    except sqlite3.Error as e:
                        logging.warning(f"SQLite error while adding column '{column}': {e}")

        except sqlite3.Error as e:
            logging.error(f"Failed to ensure students table exists: {e}")
            raise

    def _create_default_student_if_needed(self, cursor, conn):
        """Ensure the default student record exists in the students table."""
        from education_system.university_system.core import defaults

        try:
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='students'")
            table_exists = cursor.fetchone() is not None
            if not table_exists:
                logging.warning(
                    "Students table is missing; student-related authentication features may be unavailable."
                )
                return

            cursor.execute('SELECT student_id FROM students WHERE student_id = ?',
                           (defaults.DEFAULT_STUDENT_ID,))
            if not cursor.fetchone():
                timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                cursor.execute('''
                    INSERT INTO students (student_id, first_name, last_name, email_address,
                                          status, registration_datetime)
                    VALUES (?, ?, ?, ?, 'Active', ?)
                ''', (
                    defaults.DEFAULT_STUDENT_ID,
                    defaults.DEFAULT_STUDENT_FIRST_NAME,
                    defaults.DEFAULT_STUDENT_LAST_NAME,
                    defaults.DEFAULT_STUDENT_EMAIL,
                    timestamp,
                ))
                conn.commit()
                logging.info(f"Created default student record: {defaults.DEFAULT_STUDENT_ID}")
        except sqlite3.Error as exc:
            logging.warning(f"Could not inspect students table: {exc}")

    def _create_default_accounts_if_needed(self, cursor, conn, target_usernames: Optional[set[str]] = None):
        """Ensure baseline system accounts exist, creating them when missing."""
        from education_system.university_system.core import defaults

        admin_password = defaults.DEFAULT_ADMIN_PASSWORD
        staff_password = defaults.DEFAULT_STAFF_PASSWORD
        student_password = defaults.DEFAULT_STUDENT_PASSWORD

        default_accounts = {
            defaults.DEFAULT_ADMIN_USERNAME: {
                'username': defaults.DEFAULT_ADMIN_USERNAME,
                'password': admin_password,
                'first_name': defaults.DEFAULT_ADMIN_FIRST_NAME,
                'last_name': defaults.DEFAULT_ADMIN_LAST_NAME,
                'email': defaults.DEFAULT_ADMIN_EMAIL,
                'role': 'admin',
                'student_id': None
            },
            defaults.DEFAULT_STAFF_USERNAME: {
                'username': defaults.DEFAULT_STAFF_USERNAME,
                'password': staff_password,
                'first_name': defaults.DEFAULT_STAFF_FIRST_NAME,
                'last_name': defaults.DEFAULT_STAFF_LAST_NAME,
                'email': defaults.DEFAULT_STAFF_EMAIL,
                'role': 'staff',
                'student_id': None
            },
            defaults.DEFAULT_STUDENT_USERNAME: {
                'username': defaults.DEFAULT_STUDENT_USERNAME,
                'password': student_password,
                'first_name': defaults.DEFAULT_STUDENT_FIRST_NAME,
                'last_name': defaults.DEFAULT_STUDENT_LAST_NAME,
                'email': defaults.DEFAULT_STUDENT_EMAIL,
                'role': 'student',
                'student_id': defaults.DEFAULT_STUDENT_ID
            }
        }

        # Filter by target_usernames if provided
        if target_usernames:
            default_accounts = {k: v for k, v in default_accounts.items() if k in target_usernames}

        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

        for username, account_info in default_accounts.items():
            # Check if account already exists
            cursor.execute('SELECT id FROM user_accounts WHERE username = ?', (username,))
            if cursor.fetchone():
                # Account exists — sync password hash to current DEFAULT_*_PASSWORD
                try:
                    salt, password_hash = self._hash_password(account_info['password'])
                    cursor.execute(
                        'UPDATE user_accounts SET password_hash = ?, salt = ?, updated_at = ? WHERE username = ?',
                        (password_hash, salt, timestamp, username),
                    )
                except sqlite3.Error as exc:
                    logging.error(
                        f"Failed to sync password for '{username}': {exc}"
                    )

                # Check for role inconsistencies, user_id mismatch, and missing user profiles
                cursor.execute(
                    'SELECT id, role FROM users WHERE username = ?', (username,),
                )
                user_row = cursor.fetchone()
                if user_row:
                    user_id, existing_role = user_row
                    if existing_role != account_info['role']:
                        logging.warning(
                            f"Fixing role for '{username}': "
                            f"'{existing_role}' -> '{account_info['role']}'"
                        )
                        try:
                            cursor.execute(
                                'UPDATE users SET role = ?, updated_at = ? WHERE id = ?',
                                (account_info['role'], timestamp, user_id),
                            )
                        except sqlite3.Error as exc:
                            logging.error(
                                f"Failed to update role for user '{username}': {exc}"
                            )

                    # Fix user_id FK mismatch in user_accounts
                    cursor.execute(
                        'SELECT user_id FROM user_accounts WHERE username = ?',
                        (username,),
                    )
                    acct_row = cursor.fetchone()
                    if acct_row and acct_row[0] != user_id:
                        logging.warning(
                            f"Fixing user_id for '{username}' in user_accounts: "
                            f"{acct_row[0]} -> {user_id}"
                        )
                        try:
                            cursor.execute(
                                'UPDATE user_accounts SET user_id = ?, updated_at = ? WHERE username = ?',
                                (user_id, timestamp, username),
                            )
                        except sqlite3.Error as exc:
                            logging.error(
                                f"Failed to fix user_id for '{username}': {exc}"
                            )
                else:
                    # User record missing but account exists — create user profile
                    try:
                        cursor.execute(
                            '''INSERT INTO users
                               (username, first_name, last_name, email, role,
                                student_id, created_at, updated_at)
                               VALUES (?, ?, ?, ?, ?, ?, ?, ?)''',
                            (username, account_info['first_name'],
                             account_info['last_name'], account_info['email'],
                             account_info['role'], account_info['student_id'],
                             timestamp, timestamp),
                        )
                        new_user_id = cursor.lastrowid
                        cursor.execute(
                            'UPDATE user_accounts SET user_id = ? WHERE username = ?',
                            (new_user_id, username),
                        )
                        logging.info(
                            f"Created missing user profile for '{username}'"
                        )
                    except sqlite3.Error as exc:
                        logging.error(
                            f"Failed to create user record for '{username}': {exc}"
                        )
                continue  # Account already exists

            # Create user record
            cursor.execute('''
            INSERT OR IGNORE INTO users (username, first_name, last_name, email, role, student_id, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                account_info['username'],
                account_info['first_name'],
                account_info['last_name'],
                account_info['email'],
                account_info['role'],
                account_info['student_id'],
                timestamp,
                timestamp
            ))

            # Get user_id
            cursor.execute('SELECT id FROM users WHERE username = ?', (username,))
            user_result = cursor.fetchone()
            if not user_result:
                continue

            user_id = user_result[0]

            # Hash password
            salt, password_hash = self._hash_password(account_info['password'])

            # Create account
            cursor.execute('''
            INSERT INTO user_accounts (username, password_hash, salt, user_id, created_at, updated_at, is_active)
            VALUES (?, ?, ?, ?, ?, ?, 1)
            ''', (username, password_hash, salt, user_id, timestamp, timestamp))

            logging.info(f"Created default {username} account")

        conn.commit()

    def _create_configured_connection(self):
        """
        Create a new database connection with proper PRAGMA settings.

        Returns:
            sqlite3.Connection: A database connection that must be closed manually
        """
        conn = sqlite3.connect(self.db_path, timeout=30.0)
        try:
            conn.execute("PRAGMA busy_timeout = 30000")
            conn.execute("PRAGMA journal_mode = WAL")
            conn.execute("PRAGMA synchronous = NORMAL")
            conn.execute("PRAGMA foreign_keys = ON")
        except sqlite3.Error as e:
            logging.warning(f"Failed to configure connection: {e}")
        return conn

    def _hash_password(self, password, salt=None):
        """
        Hash a password with a salt using PBKDF2.

        Uses 1,000,000 iterations as recommended by OWASP for PBKDF2-SHA256.
        """
        if salt is None:
            salt = secrets.token_hex(16)

        key = hashlib.pbkdf2_hmac(
            'sha256',
            password.encode(),
            salt.encode(),
            1_000_000,  # OWASP recommendation
            dklen=64
        )

        return salt, key.hex()

    # ==========================================================================
    # CONFIGURATION AND UTILITIES
    # ==========================================================================

    def ensure_directories(self):
        """Create necessary directories"""
        import os
        for directory in [self.log_dir, self.upload_dir, self.models_dir]:
            os.makedirs(directory, exist_ok=True)

    def load_config(self):
        """Load chatbot configuration"""
        default_config = {
            "max_message_length": 500,
            "session_timeout": 1800,
            "enable_logging": True,
            "response_delay": 0.5
        }

        if os.path.exists(self.config_path):
            try:
                with open(self.config_path, 'r') as f:
                    config = json.load(f)
                return {**default_config, **config}
            except (json.JSONDecodeError, ValueError) as e:
                logging.error(f"Invalid JSON in config file: {e}")
            except (OSError, IOError) as e:
                logging.error(f"Error reading config file: {e}")

        return default_config

    def _generate_temp_password(self):
        """Generate a secure temporary password"""
        chars = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789!@#$%^&*"
        return ''.join(secrets.choice(chars) for _ in range(12))

    # ==========================================================================
    # PROPERTIES FOR BACKWARD COMPATIBILITY
    # ==========================================================================

    @property
    def current_user(self):
        """Get current logged-in user from session manager"""
        return self.session_manager.current_user if hasattr(self, 'session_manager') else None

    @current_user.setter
    def current_user(self, value):
        """Set current user in session manager"""
        if hasattr(self, 'session_manager'):
            self.session_manager.current_user = value
        else:
            # During initialization, store in instance
            self.__dict__['current_user'] = value

    @property
    def last_activity(self):
        """Get last activity timestamp from session manager"""
        return self.session_manager.last_activity if hasattr(self, 'session_manager') else None

    @last_activity.setter
    def last_activity(self, value):
        """Set last activity in session manager"""
        if hasattr(self, 'session_manager'):
            self.session_manager.last_activity = value
        else:
            # During initialization, store in instance
            self.__dict__['last_activity'] = value

    # ==========================================================================
    # LOGIN AND SESSION MANAGEMENT (Delegated to LoginManager and SessionManager)
    # ==========================================================================

    def login(self, username, password, ip_address=None):
        """
        Authenticate a user with username and password.

        Tries the shared auth database first (unified credentials across all
        education systems), then falls back to the legacy university-only
        ``user_accounts`` table for accounts that have not yet been migrated.
        """
        # ── Try shared auth first ────────────────────────────────────
        if self._shared_auth is not None:
            try:
                from education_system.shared.auth.exceptions import (
                    AuthError as SharedAuthError,
                )
                user_info = self._shared_auth.login(username, password)

                # Shared auth succeeded — check MFA
                if user_info.get("mfa_required"):
                    return {
                        "success": True,
                        "requires_2fa": True,
                        "user_id": user_info["user_id"],
                        "username": user_info["username"],
                    }

                # Extract the university role from the systems list
                role = "student"  # default
                for s in user_info.get("systems", []):
                    if s["system_key"] == "university":
                        role = s["role"]
                        break

                # Build the current_user dict in the university format
                # (includes both 'id' and 'user_id' for backward compat)
                permissions = []
                try:
                    permissions = self.permission_manager.get_user_permissions(
                        user_info["user_id"]
                    )
                except Exception:
                    pass

                # Look up university-specific profile data
                student_id = None
                legacy_user_id = None
                email = user_info.get("email", "")
                try:
                    with self.db_manager.get_connection() as conn:
                        cursor = conn.cursor()
                        cursor.execute(
                            "SELECT id, student_id, email FROM users WHERE username = ?",
                            (username,),
                        )
                        row = cursor.fetchone()
                        if row:
                            legacy_user_id = row[0]
                            student_id = row[1]
                            email = row[2] or email
                except Exception:
                    pass

                # Use legacy user ID if available so that existing
                # database references (messages, etc.) still match.
                effective_id = legacy_user_id or user_info["user_id"]

                user_dict = {
                    "id": effective_id,
                    "user_id": effective_id,
                    "shared_auth_id": user_info["user_id"],
                    "username": user_info["username"],
                    "display_name": user_info.get("display_name", username),
                    "role": role,
                    "permissions": permissions,
                    "password_reset_required": 0,
                    "student_id": student_id,
                    "email": email,
                    "systems": user_info.get("systems", []),
                }
                self.session_manager.set_current_user(user_dict)
                self.current_user = user_dict
                self.last_activity = datetime.now()

                # Log the successful login
                if ACTIVITY_LOGGER_AVAILABLE:
                    set_user(username)
                    log_login(username, success=True)

                logger.info("User '%s' logged in via shared auth", username)
                return True
            except SharedAuthError:
                # Shared auth rejected — fall through to legacy auth
                pass
            except Exception as exc:
                logger.debug("Shared auth failed for '%s': %s", username, exc)

        # ── Fall back to legacy university auth ──────────────────────
        result = self.login_manager.login(username, password)

        # Update session state if login successful
        # LoginManager.login() returns True, 'password_reset_required', dict (2FA), or False
        if result is True or result == 'password_reset_required':
            # _complete_login already set current_user in session_manager
            self.current_user = self.session_manager.current_user
            self.last_activity = datetime.now()
        elif isinstance(result, dict) and result.get('success'):
            self.last_activity = datetime.now()

        return result

    def logout(self):
        """
        Log out the current user.

        Delegates to LoginManager for logout logic.
        """
        self.login_manager.logout()

        # Clear session state
        self.current_user = None
        self.last_activity = None

    def is_logged_in(self):
        """Check if a user is currently logged in"""
        return self.current_user is not None

    def get_current_user(self):
        """Get the current logged-in user information"""
        return self.current_user

    def check_session(self):
        """Check if current session is valid"""
        return self.session_manager.check_session()

    def update_activity(self):
        """Update last activity timestamp"""
        self.session_manager.update_last_activity()
        self.last_activity = datetime.now()

    # ==========================================================================
    # USER MANAGEMENT (Delegated to UserManager)
    # ==========================================================================

    def create_user(self, username, password, email=None, first_name=None, last_name=None, role=None, student_id=None, password_reset_required=False):
        """Create a new user account"""
        return self.user_manager.create_user(
            username, password, email, first_name, last_name, role, student_id, password_reset_required
        )

    def get_user(self, user_id=None, username=None):
        """Get user information by user ID or username"""
        return self.user_manager.get_user(user_id=user_id, username=username)

    def get_user_by_username(self, username):
        """Get user information by username"""
        return self.user_manager.get_user(username=username)

    def get_user_by_id(self, user_id):
        """Get user information by user ID"""
        return self.user_manager.get_user(user_id=user_id)

    def update_user(self, user_id, **kwargs):
        """Update user information"""
        return self.user_manager.update_user(user_id, **kwargs)

    def delete_user(self, user_id):
        """Delete a user account"""
        return self.user_manager.delete_user(user_id)

    def list_users(self, role=None):
        """List all users, optionally filtered by role"""
        return self.user_manager.list_users(role)

    def activate_user(self, user_id):
        """Activate a user account"""
        return self.user_manager.activate_user(user_id)

    def deactivate_user(self, user_id):
        """Deactivate a user account"""
        return self.user_manager.deactivate_user(user_id)

    def change_password(self, username, old_password, new_password):
        """Change user password.

        Tries the shared auth system first (where most users now live),
        then falls back to the legacy university-only ``user_accounts``
        table for accounts that have not yet been migrated.
        """
        # ── Try shared auth first ────────────────────────────────────
        if self._shared_auth is not None and self.current_user:
            shared_id = self.current_user.get('shared_auth_id') or self.current_user.get('id')
            if shared_id is not None:
                try:
                    self._shared_auth.change_password(int(shared_id), old_password, new_password)
                    return True
                except Exception:
                    pass  # Fall through to legacy

        # ── Fallback to legacy user_accounts table ───────────────────
        from education_system.university_system.infrastructure.auth.managers.password_manager import change_user_password
        return change_user_password(self.db_manager, username, old_password, new_password,
                                    current_user=self.current_user)

    def reset_password(self, username, admin_user_id=None):
        """Reset user password (admin function)"""
        from education_system.university_system.infrastructure.auth.managers.password_manager import reset_user_password
        return reset_user_password(self.db_manager, username, admin_user=self.current_user)

    # ==========================================================================
    # PERMISSION MANAGEMENT (Delegated to PermissionManager)
    # ==========================================================================

    def check_permission(self, permission, raise_exception=False):
        """Check if current user has a specific permission"""
        return self.permission_manager.check_permission(permission, raise_exception)

    def has_permission(self, permission):
        """Check if current user has a specific permission"""
        return self.permission_manager.has_permission(permission)

    def get_user_permissions(self, user_id):
        """Get all permissions for a user"""
        return self.permission_manager.get_user_permissions(user_id)

    def grant_permission(self, user_id, permission_name):
        """Grant a permission to a user"""
        return self.permission_manager.set_user_permission(user_id, permission_name, granted=True)

    def revoke_permission(self, user_id, permission_name):
        """Revoke a permission from a user"""
        return self.permission_manager.set_user_permission(user_id, permission_name, granted=False)

    def set_user_permission(self, user_id, permission_name, granted=True):
        """Set a user permission (grant or revoke)"""
        return self.permission_manager.set_user_permission(user_id, permission_name, granted)

    def remove_user_permission(self, user_id, permission_name):
        """Remove a user permission entirely"""
        return self.permission_manager.remove_user_permission(user_id, permission_name)

    def list_permissions(self):
        """List all available permissions"""
        return self.permission_manager.list_permissions()

    # ==========================================================================
    # ROLE MANAGEMENT (Delegated to RoleManager)
    # ==========================================================================

    def create_role(self, role_name, description, permissions=None):
        """Create a new role"""
        return self.role_manager.create_role(role_name, description, permissions)

    def delete_role(self, role_id):
        """Delete a role"""
        return self.role_manager.delete_role(role_id)

    def list_roles(self):
        """List all roles"""
        return self.role_manager.list_roles()

    def get_role(self, role_id=None, role_name=None):
        """Get role information by ID or name"""
        return self.role_manager.get_role(role_id=role_id, role_name=role_name)

    def get_role_permissions(self, role_name):
        """Get permissions for a role"""
        role = self.role_manager.get_role(role_name=role_name)
        if role:
            return role.get('permissions', [])
        return []

    def update_role(self, role_id, **kwargs):
        """Update a role"""
        return self.role_manager.update_role(role_id, **kwargs)

    def add_role_permission(self, role_id, permission_name):
        """Add a permission to a role"""
        return self.role_manager.add_role_permission(role_id, permission_name)

    def assign_role_permission(self, role_id, permission_name):
        """Assign a permission to a role (alias for add_role_permission)"""
        return self.role_manager.add_role_permission(role_id, permission_name)

    def remove_role_permission(self, role_id, permission_name):
        """Remove a permission from a role"""
        return self.role_manager.remove_role_permission(role_id, permission_name)

    # ==========================================================================
    # MFA MANAGEMENT (Delegated to MFAManager)
    # ==========================================================================

    def enable_two_fa(self, user_id):
        """Enable two-factor authentication for a user"""
        return self.mfa_manager.enable_two_fa(user_id)

    def disable_two_fa(self, user_id):
        """Disable two-factor authentication for a user"""
        return self.mfa_manager.disable_two_fa(user_id)

    def verify_two_fa_code(self, user_id, code):
        """Verify a two-factor authentication code"""
        return self.mfa_manager.verify_two_fa_code(user_id, code)

    def generate_recovery_codes(self, user_id):
        """Generate recovery codes for two-factor authentication"""
        return self.mfa_manager.generate_recovery_codes(user_id)

    def use_recovery_code(self, user_id, code):
        """Use a recovery code for two-factor authentication"""
        return self.mfa_manager.use_recovery_code(user_id, code)

    def get_two_fa_qr_code(self, user_id):
        """Get QR code for two-factor authentication setup"""
        return self.mfa_manager.get_two_fa_qr_code(user_id)

    def complete_two_fa_login(self, user_id, username, code):
        """Complete two-factor authentication login"""
        return self.login_manager.complete_two_fa_login(user_id, username, code)

    # ==========================================================================
    # ACCOUNT SECURITY (Delegated to AccountSecurityManager)
    # ==========================================================================

    def lock_account(self, user_id):
        """Lock a user account"""
        # Deactivate the user account as a lock mechanism
        return self.user_manager.deactivate_user(user_id)

    def unlock_account(self, user_id):
        """Unlock a user account"""
        return self.user_manager.activate_user(user_id)

    def emergency_unlock(self, username, emergency_password):
        """Emergency unlock a locked account"""
        return self.account_security_manager.emergency_unlock(username, emergency_password)

    def is_account_locked(self, username):
        """Check if an account is locked"""
        remaining = self.account_security_manager.get_remaining_login_attempts(username)
        return remaining <= 0

    def get_failed_login_attempts(self, username):
        """Get number of remaining login attempts"""
        return self.account_security_manager.get_remaining_login_attempts(username)

    def get_remaining_login_attempts(self, username):
        """Get number of remaining login attempts"""
        return self.account_security_manager.get_remaining_login_attempts(username)

    def clear_failed_attempts(self, username):
        """Clear failed login attempts for a user"""
        return self.account_security_manager.reset_login_attempts(username)

    # ==========================================================================
    # ACCOUNT LINKING (Delegated to AccountLinkingManager)
    # ==========================================================================

    def create_link_request(self, target_user_id, reason=None):
        """Create a request to link another account"""
        return self.account_linking_manager.create_link_request(target_user_id, reason)

    def approve_link_request(self, request_id):
        """Approve a pending link request"""
        return self.account_linking_manager.approve_link_request(request_id)

    def reject_link_request(self, request_id, reason=None):
        """Reject a pending link request"""
        return self.account_linking_manager.reject_link_request(request_id, reason)

    def get_linked_accounts(self, user_id=None):
        """Get all linked accounts for a user"""
        return self.account_linking_manager.get_linked_accounts(user_id)

    def switch_active_role(self, linked_account_id):
        """Switch to a linked account's role"""
        return self.account_linking_manager.switch_active_role(linked_account_id)

    # ==========================================================================
    # UTILITY METHODS
    # ==========================================================================

    @staticmethod
    def _validate_username(username):
        """Validate username format"""
        from education_system.university_system.infrastructure.auth.core_utils.utils import validate_username
        return validate_username(username)

    def revert_role(self):
        """Revert to original role after role switch"""
        return self.account_linking_manager.revert_role()

    def unlink_account(self, link_id):
        """Remove a link between accounts"""
        return self.account_linking_manager.unlink_account(link_id)

    def get_link_requests(self, status='pending', direction='incoming'):
        """Get account link requests"""
        return self.account_linking_manager.get_link_requests(status, direction)

    # ==========================================================================
    # SSO MANAGEMENT (Delegated to SSOManager)
    # ==========================================================================

    def configure_sso_provider(self, provider_id, provider_type, display_name, config, **kwargs):
        """Configure an SSO provider"""
        return self.sso_manager.configure_provider(provider_id, provider_type, display_name, config, **kwargs)

    def list_sso_providers(self, enabled_only=True):
        """List configured SSO providers"""
        return self.sso_manager.list_providers(enabled_only)

    def get_sso_provider_config(self, provider_id):
        """Get SSO provider configuration"""
        return self.sso_manager.get_provider_config(provider_id)

    def delete_sso_provider(self, provider_id):
        """Delete an SSO provider"""
        return self.sso_manager.delete_provider(provider_id)

    def enable_sso_provider(self, provider_id):
        """Enable an SSO provider"""
        return self.sso_manager.enable_provider(provider_id)

    def disable_sso_provider(self, provider_id):
        """Disable an SSO provider"""
        return self.sso_manager.disable_provider(provider_id)

    # ==========================================================================
    # WEBAUTHN / FIDO2 (Delegated to WebAuthnManager)
    # ==========================================================================

    def register_webauthn_key(self, credential_name=None):
        """Begin WebAuthn key registration"""
        return self.webauthn_manager.register_key(credential_name)

    def complete_webauthn_registration(self, session_id, attestation_response):
        """Complete WebAuthn key registration"""
        return self.webauthn_manager.complete_registration(session_id, attestation_response)

    def begin_webauthn_authentication(self, username=None):
        """Begin WebAuthn authentication"""
        return self.webauthn_manager.begin_authentication(username)

    def complete_webauthn_authentication(self, session_id, assertion_response):
        """Complete WebAuthn authentication"""
        return self.webauthn_manager.complete_authentication(session_id, assertion_response)

    def list_webauthn_keys(self, user_id=None):
        """List registered WebAuthn keys"""
        return self.webauthn_manager.list_user_keys(user_id)

    def remove_webauthn_key(self, credential_id):
        """Remove a WebAuthn key"""
        return self.webauthn_manager.remove_key(credential_id)

    def rename_webauthn_key(self, credential_id, new_name):
        """Rename a WebAuthn key"""
        return self.webauthn_manager.rename_key(credential_id, new_name)

    # ==========================================================================
    # BIOMETRIC AUTHENTICATION (Delegated to BiometricManager)
    # ==========================================================================

    def enroll_biometric(self, biometric_type, data, quality_score=None):
        """Enroll a biometric template"""
        return self.biometric_manager.enroll_biometric(biometric_type, data, quality_score)

    def authenticate_biometric(self, biometric_type, data):
        """Authenticate using biometric data"""
        return self.biometric_manager.authenticate_biometric(biometric_type, data)

    def list_biometric_enrollments(self, user_id=None):
        """List biometric enrollments"""
        return self.biometric_manager.list_enrollments(user_id)

    def revoke_biometric_enrollment(self, enrollment_id):
        """Revoke a biometric enrollment"""
        return self.biometric_manager.revoke_enrollment(enrollment_id)

    # ==========================================================================
    # DELEGATED ACCESS (Delegated to DelegatedAccessManager)
    # ==========================================================================

    def create_delegation(self, delegate_user_id, scope_keys, relationship=None, expires_at=None):
        """Create a delegation granting access to another user"""
        return self.delegated_access_manager.create_delegation(
            delegate_user_id, scope_keys, relationship, expires_at
        )

    def revoke_delegation(self, delegation_id):
        """Revoke a delegation"""
        return self.delegated_access_manager.revoke_delegation(delegation_id)

    def get_delegations_for_user(self, user_id=None, direction='granted'):
        """Get delegations for a user"""
        return self.delegated_access_manager.get_delegations_for_user(user_id, direction)

    def check_delegated_permission(self, delegate_user_id, target_user_id, permission):
        """Check if delegate has a specific delegated permission"""
        return self.delegated_access_manager.check_delegated_permission(
            delegate_user_id, target_user_id, permission
        )

    def create_delegation_request(self, target_user_id, relationship, scope_keys, reason=None):
        """Request delegated access to a user's records"""
        return self.delegated_access_manager.create_delegation_request(
            target_user_id, relationship, scope_keys, reason
        )

    def approve_delegation_request(self, request_id):
        """Approve a delegation request"""
        return self.delegated_access_manager.approve_delegation_request(request_id)

    def reject_delegation_request(self, request_id, reason=None):
        """Reject a delegation request"""
        return self.delegated_access_manager.reject_delegation_request(request_id, reason)

    def get_delegation_requests(self, status='pending', direction='incoming'):
        """Get delegation requests"""
        return self.delegated_access_manager.get_delegation_requests(status, direction)

    def expire_delegations(self):
        """Expire all overdue delegations"""
        return self.delegated_access_manager.expire_delegations()

    # ==========================================================================
    # UNIFIED LOGIN (Delegated to LoginManager)
    # ==========================================================================

    def login_by_method(self, method, **kwargs):
        """Unified login dispatcher for all authentication methods"""
        return self.login_manager.login_by_method(method, **kwargs)

    def login_via_sso(self, sso_identity):
        """Login via SSO identity"""
        return self.login_manager.login_via_sso(sso_identity)

    def login_via_webauthn(self, assertion_data):
        """Login via WebAuthn assertion"""
        return self.login_manager.login_via_webauthn(assertion_data)

    def login_via_biometric(self, biometric_type, template_data):
        """Login via biometric authentication"""
        return self.login_manager.login_via_biometric(biometric_type, template_data)

    # ==========================================================================
    # DATABASE CONSISTENCY AND MAINTENANCE
    # ==========================================================================

    def fix_database_consistency(self):
        """Fix database consistency issues between users and user_accounts tables"""
        if not self.current_user or 'manage_users' not in self.current_user.get('permissions', []):
            logger.warning("You don't have permission to fix database issues.")
            return False

        try:
            conn = self._create_configured_connection()
            cursor = conn.cursor()

            logger.info("Checking database consistency...")

            # Find orphaned user records (users without accounts)
            cursor.execute('''
                SELECT u.id, u.username, u.email, u.first_name, u.last_name, u.role, u.student_id
                FROM users u
                LEFT JOIN user_accounts ua ON u.id = ua.user_id
                WHERE ua.user_id IS NULL
            ''')

            orphaned_users = cursor.fetchall()

            if orphaned_users:
                logger.info(f"Found {len(orphaned_users)} users without accounts. Creating accounts...")

                timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

                for user in orphaned_users:
                    user_id, username, email, first_name, last_name, role, student_id = user

                    # Check if an account with this username already exists
                    cursor.execute('SELECT id, user_id FROM user_accounts WHERE username = ?', (username,))
                    existing_account = cursor.fetchone()

                    if existing_account:
                        logger.info(f"Account for '{username}' already exists, skipping...")
                        continue

                    # Generate a temporary password
                    temp_password = self._generate_temp_password()
                    salt, password_hash = self._hash_password(temp_password)

                    try:
                        cursor.execute('''
                            INSERT INTO user_accounts
                            (username, password_hash, salt, user_id, created_at, updated_at, password_reset_required)
                            VALUES (?, ?, ?, ?, ?, ?, 1)
                        ''', (username, password_hash, salt, user_id, timestamp, timestamp))

                        logger.info(f"Created account for {username} with temporary password")
                    except sqlite3.IntegrityError as e:
                        logger.error(f"Failed to create account for {username}: {e}")

            # Find orphaned account records (accounts without users)
            cursor.execute('''
                SELECT ua.id, ua.username, ua.user_id
                FROM user_accounts ua
                LEFT JOIN users u ON ua.user_id = u.id
                WHERE u.id IS NULL
            ''')

            orphaned_accounts = cursor.fetchall()

            if orphaned_accounts:
                logger.info(f"Found {len(orphaned_accounts)} accounts without user profiles.")
                logger.info("These orphaned accounts will be removed to maintain database integrity...")

                for account in orphaned_accounts:
                    account_id, username, user_id = account

                    # Check if a user with this username already exists
                    cursor.execute('SELECT id FROM users WHERE username = ?', (username,))
                    existing_user = cursor.fetchone()

                    if existing_user:
                        # User exists, update the account to point to the correct user
                        logger.info(f"Updating orphaned account '{username}' to link with existing user")
                        cursor.execute('''
                            UPDATE user_accounts
                            SET user_id = ?
                            WHERE id = ?
                        ''', (existing_user[0], account_id))
                    else:
                        # No matching user exists, delete the orphaned account
                        logger.info(f"Deleting orphaned account '{username}' (no matching user found)")
                        cursor.execute('DELETE FROM user_accounts WHERE id = ?', (account_id,))

            conn.commit()
            conn.close()

            logger.info("Database consistency check completed!")
            return True

        except sqlite3.Error as e:
            logger.error(f"Database error while fixing consistency: {e}")
            return False

    def fix_missing_accounts(self):
        """Fix users that exist in users table but not in user_accounts table"""
        try:
            conn = self._create_configured_connection()
            cursor = conn.cursor()

            logger.info("Checking for users without accounts...")

            # Find users without accounts
            cursor.execute('''
            SELECT u.id, u.username, u.email, u.first_name, u.last_name, u.role
            FROM users u
            LEFT JOIN user_accounts ua ON u.id = ua.user_id
            WHERE ua.user_id IS NULL
            ''')

            orphaned_users = cursor.fetchall()

            if not orphaned_users:
                logger.info("No orphaned users found.")
                conn.close()
                return True

            logger.info(f"Found {len(orphaned_users)} users without accounts. Creating accounts...")

            for user_id, username, email, first_name, last_name, role in orphaned_users:
                password = self._generate_temp_password()

                # Create the account
                timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                salt, password_hash = self._hash_password(password)

                cursor.execute('''
                INSERT INTO user_accounts
                (username, password_hash, salt, user_id, created_at, updated_at, password_reset_required)
                VALUES (?, ?, ?, ?, ?, ?, 1)
                ''', (username, password_hash, salt, user_id, timestamp, timestamp))

                identifier = username or email or f"user-{user_id}"
                logger.info(f"Created account for {identifier} with temporary password")

            conn.commit()
            conn.close()
            logger.info("All missing accounts created successfully!")
            return True

        except Exception as e:
            logging.error(f"Error fixing missing accounts: {e}")
            return False

    def ensure_staff_account_exists(self):
        """Report whether staff accounts exist."""
        from education_system.university_system.core import defaults
        staff_username = defaults.DEFAULT_STAFF_USERNAME
        try:
            with self.db_manager.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    '''
                    SELECT ua.id
                    FROM user_accounts ua
                    WHERE ua.username = ?
                    ''',
                    (staff_username,),
                )
                if cursor.fetchone():
                    logger.info("Staff account already exists")
                    return True

                self._create_default_accounts_if_needed(cursor, conn, target_usernames={staff_username})

                cursor.execute(
                    '''
                    SELECT ua.id
                    FROM user_accounts ua
                    WHERE ua.username = ?
                    ''',
                    (staff_username,),
                )
                if cursor.fetchone():
                    logger.info(f"Staff account created successfully (username: {staff_username})")
                    return True

                logging.warning("Staff account could not be created automatically.")
                return False
        except Exception as exc:
            logging.error(f"Error verifying staff account presence: {exc}")
            return False

    def verify_default_accounts(self):
        """Summarise presence of core role accounts."""
        logger.info("Account role summary")
        try:
            conn = self._create_configured_connection()
            cursor = conn.cursor()
            cursor.execute(
                '''
                SELECT u.role, COUNT(ua.id) AS account_count
                FROM user_accounts ua
                JOIN users u ON ua.user_id = u.id
                GROUP BY u.role
                '''
            )
            role_counts = {role: count for role, count in cursor.fetchall()}

            required_roles = ['admin', 'staff', 'student']
            missing_roles = []

            for role in required_roles:
                count = role_counts.get(role, 0)
                if count == 0:
                    logger.warning(f"No active accounts found for role '{role}'.")
                    missing_roles.append(role)
                else:
                    logger.info(f"{count} account(s) found for role '{role}'.")

            other_roles = {role: count for role, count in role_counts.items() if role not in required_roles}
            if other_roles:
                logger.info("Additional roles detected:")
                for role, count in sorted(other_roles.items()):
                    logger.info(f"{role}: {count} account(s)")

            if missing_roles:
                logger.warning("Provision accounts for missing roles using the administration interface.")
                return False

            logger.info("Core roles are represented.")
            return True
        except sqlite3.Error as exc:
            logger.error(f"Unable to summarise account roles: {exc}")
            return False
        finally:
            conn.close()

    # ==========================================================================
    # CHATBOT INTEGRATION
    # ==========================================================================

    def initialize_chatbot_integration(self):
        """Initialize chatbot integration with comprehensive error handling"""
        if CHATBOT_AVAILABLE:
            try:
                logger.info("Initializing chatbot integration...")
                self.chatbot = UniversityChatbot(db_path=self.db_path)

                # Verify the chatbot has required attributes
                required_attrs = ['app', 'config', 'conversation_history', 'auth_system']
                missing_attrs = [attr for attr in required_attrs if not hasattr(self.chatbot, attr)]

                if missing_attrs:
                    logger.warning(f"Chatbot missing attributes: {missing_attrs}")
                    # Add missing attributes
                    for attr in missing_attrs:
                        setattr(self.chatbot, attr, None)

                self.chatbot.set_auth_system(self)
                logger.info("Chatbot integration initialized successfully")
                return True

            except (ImportError, OptionalDependencyError) as e:
                logger.warning(f"Chatbot module not available: {e}")
                self._create_fallback_chatbot()
                return False
            except (AttributeError, TypeError) as e:
                logger.warning(f"Chatbot integration failed (attribute error): {e}")
                logger.debug(f"Error type: {type(e).__name__}")
                self._create_fallback_chatbot()
                return False
            except sqlite3.Error as e:
                logger.warning(f"Chatbot integration failed (database error): {e}")
                self._create_fallback_chatbot()
                return False
        else:
            logger.info("Chatbot module not available")
            self.chatbot = None
            return False

    def _create_fallback_chatbot(self):
        """Create a minimal fallback chatbot"""
        class FallbackChatbot:
            def __init__(self):
                self.enabled = False

            def process_message(self, msg, user, session_id=None, voice=False):
                return "Chatbot temporarily unavailable. Please try again later."

            def run_authenticated_console_interface(self):
                print("Chatbot is currently unavailable.")

            def set_auth_system(self, auth):
                """Set the authentication system reference"""
                self.auth_system = auth

            def get_conversation_history(self, user, limit=10):
                return []

        self.chatbot = FallbackChatbot()
        logger.info("Fallback chatbot created")



    def setup_chatbot_permissions(self):
        """
        Setup chatbot-specific permissions in the database.

        Delegates to the chatbot_integration module's setup_chatbot_permissions function.
        """
        from education_system.university_system.infrastructure.auth.integrations.chatbot_integration import (
            setup_chatbot_permissions as setup_perms
        )
        return setup_perms(self)

# ==========================================================================
# MODULE-LEVEL TEST FUNCTIONS
# ==========================================================================

def test_authentication_fix():
    """Run diagnostics against authentication data without seeding demo users."""
    print("=== AUTHENTICATION DATA CHECK ===")

    auth = UserAuth()

    # Summarise role coverage
    auth.verify_default_accounts()
    auth.ensure_staff_account_exists()

    # Inspect for orphaned records and locked accounts
    with auth.db_manager.get_connection() as conn:
        cursor = conn.cursor()

        cursor.execute(
            '''
            SELECT COUNT(*)
            FROM users u
            LEFT JOIN user_accounts ua ON u.id = ua.user_id
            WHERE ua.user_id IS NULL
            '''
        )
        orphan_count = cursor.fetchone()[0]
        if orphan_count:
            print(f"⚠️  {orphan_count} user record(s) do not have login accounts. Call fix_missing_accounts() if appropriate.")
        else:
            print("✓ All user records have corresponding login accounts.")

        cursor.execute("SELECT COUNT(*) FROM user_accounts WHERE is_active = 0")
        locked_accounts = cursor.fetchone()[0]
        if locked_accounts:
            print(f"⚠️  {locked_accounts} account(s) are marked inactive.")
        else:
            print("✓ No inactive accounts detected.")


def test_authentication_with_ai_detector():
    """Summarise AI detector permissions without relying on seeded accounts."""
    print("=== TESTING AI DETECTOR PERMISSIONS ===")

    try:
        auth = UserAuth()

        ai_permissions = [
            'access_ai_detector',
            'analyze_submissions',
            'view_own_ai_results',
            'view_any_ai_results',
            'manage_ai_whitelist',
            'configure_ai_detector',
            'view_ai_statistics',
        ]

        with auth.db_manager.get_connection() as conn:
            cursor = conn.cursor()

            cursor.execute(
                '''
                SELECT permission_name
                FROM permissions
                WHERE permission_name IN ({})
                '''.format(','.join('?' for _ in ai_permissions)),
                ai_permissions,
            )
            present_perms = {row[0] for row in cursor.fetchall()}
            missing_perms = sorted(set(ai_permissions) - present_perms)

            if missing_perms:
                print(f"❌ Missing AI detector permissions: {', '.join(missing_perms)}")
            else:
                print("✓ All AI detector permissions are registered.")

            cursor.execute(
                '''
                SELECT DISTINCT u.username, u.role
                FROM user_accounts ua
                JOIN users u ON ua.user_id = u.id
                JOIN roles r ON r.role_name = u.role
                JOIN role_permissions rp ON rp.role_id = r.id
                JOIN permissions p ON p.id = rp.permission_id
                WHERE p.permission_name IN ({})
                ORDER BY u.role, u.username
                '''.format(','.join('?' for _ in ai_permissions)),
                ai_permissions,
            )
            rows = cursor.fetchall()

            if rows:
                print("\nUsers currently mapped to AI detector permissions:")
                for username, role in rows:
                    print(f"• {username} ({role})")
            else:
                print("\n⚠️  No user accounts are currently mapped to AI detector permissions.")

    except Exception as e:
        print(f"❌ Error testing AI detector permissions: {e}")
        traceback.print_exc()


def test_plagiarism_authentication():
    """Test plagiarism system authentication"""
    print("=== TESTING PLAGIARISM AUTHENTICATION ===")

    try:
        auth = UserAuth()

        plagiarism_permissions = [
            'check_plagiarism',
            'manage_plagiarism_system',
            'submit_document',
            'check_plagiarism_any_course',
            'access_plagiarism_menu',
        ]

        with auth.db_manager.get_connection() as conn:
            cursor = conn.cursor()

            cursor.execute(
                '''
                SELECT permission_name
                FROM permissions
                WHERE permission_name IN ({})
                '''.format(','.join('?' for _ in plagiarism_permissions)),
                plagiarism_permissions,
            )
            present_perms = {row[0] for row in cursor.fetchall()}
            missing_perms = sorted(set(plagiarism_permissions) - present_perms)

            if missing_perms:
                print(f"❌ Missing plagiarism permissions: {', '.join(missing_perms)}")
            else:
                print("✓ All plagiarism permissions are registered.")

    except Exception as e:
        print(f"❌ Error testing plagiarism permissions: {e}")
        traceback.print_exc()


def simple_login_test(username=None, password=None):
    """Simple login test function"""
    auth = UserAuth()

    if username is None:
        username = input("Username: ")
    if password is None:
        import getpass
        password = getpass.getpass("Password: ")

    result = auth.login(username, password)

    if result.get('success'):
        print(f"✓ Login successful! Welcome, {result['user']['first_name']}!")
        print(f"Role: {result['user']['role']}")
        print(f"Permissions: {len(result['user'].get('permissions', []))} permission(s)")
    else:
        print(f"✗ Login failed: {result.get('error')}")

    return auth


def test_trip_integration():
    """Test trip management integration"""
    print("=== TESTING TRIP INTEGRATION ===")

    try:
        auth = UserAuth()

        trip_permissions = [
            'manage_trips',
            'create_trips',
            'view_trips',
            'register_for_trips',
            'view_own_trip_registrations',
            'cancel_trip_registration',
        ]

        with auth.db_manager.get_connection() as conn:
            cursor = conn.cursor()

            cursor.execute(
                '''
                SELECT permission_name
                FROM permissions
                WHERE permission_name IN ({})
                '''.format(','.join('?' for _ in trip_permissions)),
                trip_permissions,
            )
            present_perms = {row[0] for row in cursor.fetchall()}
            missing_perms = sorted(set(trip_permissions) - present_perms)

            if missing_perms:
                print(f"❌ Missing trip permissions: {', '.join(missing_perms)}")
            else:
                print("✓ All trip permissions are registered.")

    except Exception as e:
        print(f"❌ Error testing trip permissions: {e}")
        traceback.print_exc()


def quick_test_integration():
    """Quick integration test"""
    print("=== QUICK INTEGRATION TEST ===")

    try:
        auth = UserAuth()
        print("✓ UserAuth initialized successfully")

        # Test login with default admin
        from education_system.university_system.core.defaults import DEFAULT_ADMIN_USERNAME, DEFAULT_ADMIN_PASSWORD
        result = auth.login(DEFAULT_ADMIN_USERNAME, DEFAULT_ADMIN_PASSWORD)
        if result.get('success'):
            print("✓ Admin login successful")
            auth.logout()
            print("✓ Logout successful")
        else:
            print(f"✗ Admin login failed: {result.get('error')}")

        print("\n✅ Quick integration test completed!")

    except Exception as e:
        print(f"❌ Integration test failed: {e}")
        traceback.print_exc()


def setup_default_accounts():
    """Standalone helper to ensure baseline accounts exist."""
    print("=== ACCOUNT SETUP ===")
    try:
        auth = UserAuth()
        with auth.db_manager.get_connection() as conn:
            cursor = conn.cursor()
            auth._create_default_accounts_if_needed(cursor, conn)

        auth.verify_default_accounts()
        print("Setup completed.")
        return True
    except sqlite3.Error as e:
        print(f"❌ Database error ensuring default accounts: {e}")
        return False
    except (AuthenticationError, PermissionDeniedError) as e:
        print(f"❌ Auth error ensuring default accounts: {e}")
        return False


# ==========================================================================
# MODULE EXECUTION
# ==========================================================================

if __name__ == "__main__":
    print("UserAuth Core Module")
    print("=" * 50)
    print("This module provides the central authentication orchestration layer.")
    print("Available test functions:")
    print("  - test_authentication_fix()")
    print("  - test_authentication_with_ai_detector()")
    print("  - test_plagiarism_authentication()")
    print("  - simple_login_test()")
    print("  - test_trip_integration()")
    print("  - quick_test_integration()")
    print("  - setup_default_accounts()")
    print("\nRun quick_test_integration() for a basic test...")
    print("=" * 50)

    # Run quick test
    quick_test_integration()
