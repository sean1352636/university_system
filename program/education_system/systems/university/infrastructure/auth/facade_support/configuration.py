"""Extracted backwards-compatible UserAuth methods."""
from ..facade_support import *

class AuthFacadeSupportConfigurationMixin:
    def _set_safe_defaults(self, db_path):
        """Set minimal safe defaults after initialization failure"""
        self._shared_auth = None
        self.current_user = None
        self.last_activity = None
        self.session_timeout = 30
        self.login_attempts = {}
        self.max_attempts = 3
        self.lockout_time = 15
        self.config = {}
        self.conversation_history = {}
        self.auth_system = None
        # Preserve the already-normalized db_path if available, otherwise normalize now
        if not hasattr(self, 'db_path') or self.db_path is None:
            self.db_path = (
                os.fspath(paths.UNIVERSITY_DEFAULT_DB_PATH)
                if db_path is None
                else db_path
            )

        # Still try to initialize database and managers
        try:
            # Import managers here to avoid circular dependencies
            from education_system.systems.university.infrastructure.auth.managers.database_manager import DatabaseConnectionManager
            from education_system.systems.university.infrastructure.auth.managers import password_manager
            from education_system.systems.university.infrastructure.auth.managers.session_manager import SessionManager
            from education_system.systems.university.infrastructure.auth.managers.user_manager import UserManager
            from education_system.systems.university.infrastructure.auth.managers.permission_manager import PermissionManager
            from education_system.systems.university.infrastructure.auth.managers.role_manager import RoleManager
            from education_system.systems.university.infrastructure.auth.managers.mfa_manager import MFAManager
            from education_system.systems.university.infrastructure.auth.managers.account_security import AccountSecurityManager
            from education_system.systems.university.infrastructure.auth.managers.login_manager import LoginManager
            from education_system.systems.university.infrastructure.auth.managers.account_linking_manager import AccountLinkingManager
            from education_system.systems.university.infrastructure.auth.managers.sso_manager import SSOManager
            from education_system.systems.university.infrastructure.auth.managers.webauthn_manager import WebAuthnManager
            from education_system.systems.university.infrastructure.auth.managers.biometric_manager import BiometricManager
            from education_system.systems.university.infrastructure.auth.managers.delegated_access_manager import DelegatedAccessManager
            from education_system.systems.university.infrastructure.auth.managers import activity_logger
            from education_system.systems.university.infrastructure.auth.core_utils.utils import (
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
