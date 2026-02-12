"""
Authentication and Authorization Package

Provides authentication and authorization features including:
- User authentication with secure password hashing
- Multi-Factor Authentication (MFA) support
- MFA enforcement for privileged roles
- Role-based access control (RBAC)
- Session management
- Permission decorators

Refactored Structure (v5.0.0)
-----------------------------
The authentication system has been modularized into focused components:
- core.py: Main UserAuth class
- constants.py: Role and permission definitions
- database_manager.py: Connection management
- password_manager.py: Password operations
- login_manager.py: Login/logout logic
- session_manager.py: Session tracking
- user_manager.py: User CRUD operations
- permission_manager.py: Permission management
- role_manager.py: Role management
- mfa_manager.py: Multi-factor authentication
- account_security.py: Account lockout and security
- activity_logger.py: Audit trail logging
- chatbot_integration.py: Chatbot features
- module_permissions.py: Module-specific permissions
- cli_menus.py: CLI interfaces
- global_auth.py: Global auth instance
- utils.py: Validation and helpers

All original functionality is preserved with improved maintainability.
"""

# Core authentication - import from refactored modules
from university_system.infrastructure.auth.core import (
    UserAuth,
    test_authentication_fix,
    test_authentication_with_ai_detector,
    test_plagiarism_authentication,
    simple_login_test,
    test_trip_integration,
    quick_test_integration,
    setup_default_accounts,
)

# Import from organized subdirectories
from university_system.infrastructure.auth.core_utils import (
    # Global auth functions
    get_current_user,
    set_auth_instance,
    get_auth_instance,
    clear_auth_instance,
    is_user_logged_in,
    get_current_user_id,
    get_current_username,
    get_current_user_role,
    get_global_auth,
    set_global_auth,
    reset_global_auth,
    # Constants
    ROLES,
    PERMISSIONS,
    DEFAULT_SESSION_TIMEOUT,
    DEFAULT_MAX_LOGIN_ATTEMPTS,
    DEFAULT_LOCKOUT_TIME,
    PASSWORD_MIN_LENGTH,
    PBKDF2_ITERATIONS,
    # Utility functions
    validate_username,
    validate_password,
    validate_email,
    generate_temp_password,
    ensure_students_table,
    get_default_password,
    infer_role_for_username,
)

# Manager classes and modules
from university_system.infrastructure.auth.managers import (
    DatabaseConnectionManager,
    LoginManager,
    SessionManager,
    UserManager,
    PermissionManager,
    RoleManager,
    MFAManager,
    AccountSecurityManager,
    SSOManager,
    WebAuthnManager,
    BiometricManager,
    DelegatedAccessManager,
    password_manager,  # Function-based module
    activity_logger,   # Function-based module
)

# Account Linking Manager
from university_system.infrastructure.auth.managers.account_linking_manager import AccountLinkingManager

# Integration modules
from university_system.infrastructure.auth.integrations import (
    # Chatbot integration
    test_chatbot_integration,
    create_sample_chatbot_data,
    # Module permissions
    initialize_complete_system,
    init_trip_db,
    setup_trip_permissions,
    set_trip_auth,
    integrate_trip_management_with_main,
    add_finance_permissions,
    fix_alumni_permissions,
    get_health_role_permissions,
    add_calendar_permissions,
    setup_ai_detector_permissions,
    verify_ai_detector_setup,
    add_ai_detector_permissions_to_database,
    add_plagiarism_permissions,
)

# CLI menu functions
from university_system.infrastructure.auth.cli import (
    display_auth_menu,
    display_user_management_menu,
    display_role_management_menu,
    display_my_account_menu,
    display_mfa_settings_menu,
    display_chatbot_integration_menu,
)

# Permission decorators - wrapped to handle missing functionality gracefully
def require_permission(permission):
    """Decorator to require a specific permission for a function."""
    def decorator(func):
        from functools import wraps
        @wraps(func)
        def wrapper(*args, **kwargs):
            from university_system.infrastructure.shared_context import get_auth
            auth = get_auth()
            if auth and hasattr(auth, 'has_permission'):
                if not auth.has_permission(permission):
                    raise PermissionError(f"Permission '{permission}' required")
            return func(*args, **kwargs)
        return wrapper
    return decorator

def require_role(role):
    """Decorator to require a specific role for a function."""
    def decorator(func):
        from functools import wraps
        @wraps(func)
        def wrapper(*args, **kwargs):
            from university_system.infrastructure.shared_context import get_auth
            auth = get_auth()
            if auth and hasattr(auth, 'get_user_role'):
                user_role = auth.get_user_role()
                if user_role != role:
                    raise PermissionError(f"Role '{role}' required, but user has '{user_role}'")
            return func(*args, **kwargs)
        return wrapper
    return decorator

# Alias for backward compatibility
permission_required = require_permission

# MFA Services (optional imports)
try:
    from university_system.infrastructure.auth.mfa_service import (
        MFAService,
        setup_totp,
        verify_totp,
        generate_sms_otp,
        verify_sms_otp,
    )
    MFA_AVAILABLE = True
except ImportError:
    MFAService = None
    MFA_AVAILABLE = False

try:
    from university_system.infrastructure.auth.mfa_integration import integrate_mfa_with_auth
    MFA_INTEGRATION_AVAILABLE = True
except ImportError:
    MFA_INTEGRATION_AVAILABLE = False

try:
    from university_system.infrastructure.auth.email_otp_service import EmailOTPService
    EMAIL_OTP_AVAILABLE = True
except ImportError:
    EmailOTPService = None
    EMAIL_OTP_AVAILABLE = False

try:
    from university_system.infrastructure.auth.sms_provider import SMSProvider
    SMS_PROVIDER_AVAILABLE = True
except ImportError:
    SMSProvider = None
    SMS_PROVIDER_AVAILABLE = False

# MFA Enforcement
try:
    from university_system.infrastructure.auth.mfa_enforcement import (
        MFAEnforcement,
        get_mfa_enforcement,
        require_mfa_for_role,
        check_mfa_compliance,
        enforce_mfa_on_login,
        get_non_compliant_users,
        mfa_required,
    )
    MFA_ENFORCEMENT_AVAILABLE = True
except ImportError:
    MFAEnforcement = None
    MFA_ENFORCEMENT_AVAILABLE = False

__all__ = [
    # Core authentication
    'UserAuth',
    'get_current_user',
    'set_auth_instance',
    'get_auth_instance',
    'clear_auth_instance',
    'is_user_logged_in',
    'get_current_user_id',
    'get_current_username',
    'get_current_user_role',
    'get_global_auth',
    'set_global_auth',
    'reset_global_auth',

    # Manager classes
    'DatabaseConnectionManager',
    'LoginManager',
    'SessionManager',
    'UserManager',
    'PermissionManager',
    'RoleManager',
    'MFAManager',
    'AccountSecurityManager',
    'AccountLinkingManager',
    'SSOManager',
    'WebAuthnManager',
    'BiometricManager',
    'DelegatedAccessManager',

    # Function-based manager modules
    'password_manager',
    'activity_logger',

    # Constants
    'ROLES',
    'PERMISSIONS',
    'DEFAULT_SESSION_TIMEOUT',
    'DEFAULT_MAX_LOGIN_ATTEMPTS',
    'DEFAULT_LOCKOUT_TIME',
    'PASSWORD_MIN_LENGTH',
    'PBKDF2_ITERATIONS',

    # Utility functions
    'validate_username',
    'validate_password',
    'validate_email',
    'generate_temp_password',
    'ensure_students_table',
    'get_default_password',
    'infer_role_for_username',

    # Module permissions
    'initialize_complete_system',
    'init_trip_db',
    'setup_trip_permissions',
    'set_trip_auth',
    'integrate_trip_management_with_main',
    'add_finance_permissions',
    'fix_alumni_permissions',
    'get_health_role_permissions',
    'add_calendar_permissions',
    'setup_ai_detector_permissions',
    'verify_ai_detector_setup',
    'add_ai_detector_permissions_to_database',
    'add_plagiarism_permissions',

    # CLI menus
    'display_auth_menu',
    'display_user_management_menu',
    'display_role_management_menu',
    'display_my_account_menu',
    'display_mfa_settings_menu',
    'display_chatbot_integration_menu',

    # Chatbot
    'test_chatbot_integration',
    'create_sample_chatbot_data',

    # Test functions
    'test_authentication_fix',
    'test_authentication_with_ai_detector',
    'test_plagiarism_authentication',
    'simple_login_test',
    'test_trip_integration',
    'quick_test_integration',
    'setup_default_accounts',

    # Permission decorators
    'require_permission',
    'require_role',
    'permission_required',

    # MFA (optional)
    'MFAService',
    'MFA_AVAILABLE',
    'MFA_INTEGRATION_AVAILABLE',
    'EMAIL_OTP_AVAILABLE',
    'SMS_PROVIDER_AVAILABLE',

    # MFA Enforcement
    'MFAEnforcement',
    'MFA_ENFORCEMENT_AVAILABLE',
    'get_mfa_enforcement',
    'require_mfa_for_role',
    'check_mfa_compliance',
    'enforce_mfa_on_login',
    'get_non_compliant_users',
    'mfa_required',
]
