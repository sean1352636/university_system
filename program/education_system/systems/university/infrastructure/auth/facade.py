"""Public backwards-compatible UserAuth API."""
from .facade_support import *
from .context import set_auth_instance
from .facade_support.configuration import AuthFacadeSupportConfigurationMixin
from .facade_support.state import AuthFacadeSupportStateMixin
from .facade_support.shared_auth import AuthFacadeSupportSharedAuthMixin
from .facade_support.legacy_migration import AuthFacadeSupportLegacyMigrationMixin
from .facade_support.optional_interfaces import AuthFacadeSupportOptionalInterfacesMixin
from .facade_components.authentication.password_login import AuthAuthenticationPasswordLoginMixin
from .facade_components.authentication.service import AuthAuthenticationServiceMixin
from .facade_components.authentication.federated_login import AuthAuthenticationFederatedLoginMixin
from .facade_components.authentication.webauthn_login import AuthAuthenticationWebauthnLoginMixin
from .facade_components.authentication.biometric_login import AuthAuthenticationBiometricLoginMixin
from .facade_components.authentication.lockout_policy import AuthAuthenticationLockoutPolicyMixin
from .facade_components.bootstrap.schema import AuthBootstrapSchemaMixin
from .facade_components.bootstrap.default_accounts import AuthBootstrapDefaultAccountsMixin
from .facade_components.bootstrap.consistency_checks import AuthBootstrapConsistencyChecksMixin
from .facade_components.credentials.passwords import AuthCredentialsPasswordsMixin
from .facade_components.credentials.mfa import AuthCredentialsMfaMixin
from .facade_components.persistence.users import AuthPersistenceUsersMixin
from .facade_components.persistence.permissions import AuthPersistencePermissionsMixin
from .facade_components.accounts.account_linking import AuthAccountsAccountLinkingMixin
from .facade_components.accounts.delegated_access import AuthAccountsDelegatedAccessMixin
from .facade_components.federation.service import AuthFederationServiceMixin
from .facade_components.federation.webauthn import AuthFederationWebauthnMixin
from .facade_components.federation.biometrics import AuthFederationBiometricsMixin
from .facade_support.optional_interfaces import MinimalVoiceInterface

class UserAuth(
    AuthFacadeSupportConfigurationMixin,
    AuthFacadeSupportStateMixin,
    AuthFacadeSupportSharedAuthMixin,
    AuthFacadeSupportLegacyMigrationMixin,
    AuthFacadeSupportOptionalInterfacesMixin,
    AuthAuthenticationPasswordLoginMixin,
    AuthAuthenticationServiceMixin,
    AuthAuthenticationFederatedLoginMixin,
    AuthAuthenticationWebauthnLoginMixin,
    AuthAuthenticationBiometricLoginMixin,
    AuthAuthenticationLockoutPolicyMixin,
    AuthBootstrapSchemaMixin,
    AuthBootstrapDefaultAccountsMixin,
    AuthBootstrapConsistencyChecksMixin,
    AuthCredentialsPasswordsMixin,
    AuthCredentialsMfaMixin,
    AuthPersistenceUsersMixin,
    AuthPersistencePermissionsMixin,
    AuthAccountsAccountLinkingMixin,
    AuthAccountsDelegatedAccessMixin,
    AuthFederationServiceMixin,
    AuthFederationWebauthnMixin,
    AuthFederationBiometricsMixin,
):
    """Backwards-compatible authentication coordinator."""

    _init_lock = threading.Lock()
    _db_initialized = False

    from education_system.systems.university.infrastructure.auth.managers.activity_logger import log_activity_with_connection
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
            self.max_attempts = 3
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

            self.db_path = _normalise_path(db_path, paths.UNIVERSITY_DEFAULT_DB_PATH)
            self.config_path = _normalise_path(
                config_path, paths.UNIVERSITY_CHATBOT_CONFIG_PATH
            )
            self.log_dir = os.fspath(paths.UNIVERSITY_LOG_DIR)
            self.upload_dir = os.fspath(paths.UNIVERSITY_CHATBOT_UPLOAD_DIR)
            self.models_dir = os.fspath(paths.UNIVERSITY_CHATBOT_MODELS_DIR)

            # Authentication system integration
            self.auth_system = None
            self.authenticated_sessions = {}
            self.conversation_contexts = {}

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

            # Initialize database manager
            self.db_manager = DatabaseConnectionManager(self.db_path)

            # Load configuration FIRST
            self.config = self.load_config()

            # Initialize directories
            self.ensure_directories()

            # Voice interface is initialised lazily (see the voice_interface
            # property). Probing is_chatbot_available() here used to load the
            # whole chatbot tree — including Flask — adding ~1s to every login,
            # for a feature most sessions never touch.
            self._voice_interface = None

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
            from education_system.systems.university.infrastructure.auth.managers import activity_logger

            def activity_logger_wrapper(username, action, details=None, user_id=None):
                """Wrapper for activity_logger that binds db_path"""
                return activity_logger.log_activity(self.db_path, username, action, details, user_id)

            # Import validators for UserManager
            from education_system.systems.university.infrastructure.auth.core_utils.utils import (
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
                from education_system.platform.identity.auth.schema import (
                    initialise_auth_db as _init_shared_db,
                    seed_default_users as _seed_shared,
                )
                from education_system.platform.identity.auth.core import (
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

__all__ = ["UserAuth", "MinimalVoiceInterface", "set_auth_instance"]
