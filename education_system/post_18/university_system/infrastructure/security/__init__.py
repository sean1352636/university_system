"""
Security Infrastructure Package.

Provides security features including:
- Rate limiting for login protection
- Comprehensive audit trail logging
- Immutable (blockchain-style) audit log
- Real-time security alerting (email, Slack, SMS)
- Data encryption
- Session management with remember me support (NEW)
- Security dashboard
- Secure password generation
- Secure file upload handling with comprehensive validation (ENHANCED)
- KMS integration for key management
- Security headers for web applications
- Unified security integration (NEW)
"""

from education_system.post_18.university_system.infrastructure.security.rate_limiter import (
    RateLimiter,
    RateLimitExceeded,
    RateLimitConfig,
    rate_limit,
    login_limiter,
    password_reset_limiter,
)

from education_system.post_18.university_system.infrastructure.security.audit_trail import (
    AuditLogger,
    AuditEntry,
    AuditAction,
    audit_data_access,
    log_activity,
    get_audit_logger,
)

from education_system.post_18.university_system.infrastructure.security.password_generator import (
    generate_secure_password,
    generate_simple_password,
    generate_temp_password,
    generate_passphrase,
    check_password_strength,
)

# Audit log viewer is a Tk-based GUI. Import it lazily (PEP 562) so that merely
# using the security package for login/startup (rate limiting, audit logging,
# alerts) does NOT drag in the whole GUI dashboard tree (~1s of import time:
# security_dashboard_gui -> mfa_admin_gui/mfa_gui). The names below still resolve
# on first access via __getattr__, so `from ...security import AuditLogViewerGUI`
# keeps working for code that actually needs the viewer.
_LAZY_ATTRS = {
    "AuditLogViewerGUI": "education_system.post_18.university_system.modules.shared.gui.security.audit_log_viewer_gui",
    "AnomalyDetector": "education_system.post_18.university_system.modules.shared.gui.security.audit_log_viewer_gui",
    "show_audit_log_viewer": "education_system.post_18.university_system.modules.shared.gui.security.audit_log_viewer_gui",
}


def __getattr__(name):  # PEP 562 module-level lazy attribute loader
    module_path = _LAZY_ATTRS.get(name)
    if module_path is not None:
        import importlib
        return getattr(importlib.import_module(module_path), name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


from education_system.post_18.university_system.infrastructure.security.file_upload import (
    SecureFileUpload,
    get_upload_handler,
    validate_upload,
    save_upload,
    secure_filename,
)

from education_system.post_18.university_system.infrastructure.security.kms_integration import (
    KMSIntegration,
    KMSError,
    KMSProviderNotConfigured,
    KMSKeyRetrievalError,
    is_kms_enabled,
    get_kms_provider,
    get_kms_integration,
)

from education_system.post_18.university_system.infrastructure.security.flask_security_headers import (
    add_security_headers,
    init_security_headers,
    create_security_headers_blueprint,
    get_default_csp,
    get_hsts_value,
)

from education_system.post_18.university_system.infrastructure.security.immutable_audit_log import (
    ImmutableAuditLog,
    get_immutable_audit_log,
    log_security_event,
    verify_audit_log_integrity,
    AuditAction as ImmutableAuditAction,
)

from education_system.post_18.university_system.infrastructure.security.security_alerts import (
    SecurityAlertManager,
    get_alert_manager,
    send_security_alert,
    alert_suspicious_login,
    alert_brute_force_attempt,
    alert_unauthorized_access,
    alert_data_exfiltration,
    alert_account_lockout,
    alert_privilege_escalation,
    alert_configuration_change,
)

# NEW: Remember Me & Enhanced Security
try:
    from education_system.post_18.university_system.infrastructure.security.remember_me import (
        RememberMeManager,
        RememberMeToken,
        remember_me_manager,
    )
    REMEMBER_ME_AVAILABLE = True
except ImportError:
    REMEMBER_ME_AVAILABLE = False
    RememberMeManager = None
    RememberMeToken = None
    remember_me_manager = None

# NEW: File Upload Validator
try:
    from education_system.post_18.university_system.infrastructure.security.file_upload_validator import (
        FileUploadValidator,
        UploadValidationResult,
        document_validator,
        image_validator,
        avatar_validator,
        strict_validator,
    )
    FILE_UPLOAD_VALIDATOR_AVAILABLE = True
except ImportError:
    FILE_UPLOAD_VALIDATOR_AVAILABLE = False
    FileUploadValidator = None
    UploadValidationResult = None
    document_validator = None
    image_validator = None
    avatar_validator = None
    strict_validator = None

# NEW: Security Integration
try:
    from education_system.post_18.university_system.infrastructure.security.security_integration import (
        SecurityManager,
        get_security_manager,
        login_with_security,
        validate_upload as validate_upload_secure,
        check_rate_limit as check_rate_limit_secure,
        validate_input as validate_input_secure,
    )
    SECURITY_INTEGRATION_AVAILABLE = True
except ImportError:
    SECURITY_INTEGRATION_AVAILABLE = False
    SecurityManager = None
    get_security_manager = None
    login_with_security = None
    validate_upload_secure = None
    check_rate_limit_secure = None
    validate_input_secure = None

__all__ = [
    # Rate Limiting
    'RateLimiter',
    'RateLimitExceeded',
    'RateLimitConfig',
    'rate_limit',
    'login_limiter',
    'password_reset_limiter',
    # Audit Trail
    'AuditLogger',
    'AuditEntry',
    'AuditAction',
    'audit_data_access',
    'log_activity',
    'get_audit_logger',
    # Password Generation
    'generate_secure_password',
    'generate_simple_password',
    'generate_temp_password',
    'generate_passphrase',
    'check_password_strength',
    # Audit Log Viewer
    'AuditLogViewerGUI',
    'AnomalyDetector',
    'show_audit_log_viewer',
    # Secure File Upload
    'SecureFileUpload',
    'get_upload_handler',
    'validate_upload',
    'save_upload',
    'secure_filename',
    # KMS Integration
    'KMSIntegration',
    'KMSError',
    'KMSProviderNotConfigured',
    'KMSKeyRetrievalError',
    'is_kms_enabled',
    'get_kms_provider',
    'get_kms_integration',
    # Flask Security Headers
    'add_security_headers',
    'init_security_headers',
    'create_security_headers_blueprint',
    'get_default_csp',
    'get_hsts_value',
    # Immutable Audit Log
    'ImmutableAuditLog',
    'get_immutable_audit_log',
    'log_security_event',
    'verify_audit_log_integrity',
    'ImmutableAuditAction',
    # Security Alerts
    'SecurityAlertManager',
    'get_alert_manager',
    'send_security_alert',
    'alert_suspicious_login',
    'alert_brute_force_attempt',
    'alert_unauthorized_access',
    'alert_data_exfiltration',
    'alert_account_lockout',
    'alert_privilege_escalation',
    'alert_configuration_change',
    # NEW: Remember Me (v5.10.0)
    'RememberMeManager',
    'RememberMeToken',
    'remember_me_manager',
    'REMEMBER_ME_AVAILABLE',
    # NEW: File Upload Validator (v5.10.0)
    'FileUploadValidator',
    'UploadValidationResult',
    'document_validator',
    'image_validator',
    'avatar_validator',
    'strict_validator',
    'FILE_UPLOAD_VALIDATOR_AVAILABLE',
    # NEW: Security Integration (v5.10.0)
    'SecurityManager',
    'get_security_manager',
    'login_with_security',
    'validate_upload_secure',
    'check_rate_limit_secure',
    'validate_input_secure',
    'SECURITY_INTEGRATION_AVAILABLE',
]
