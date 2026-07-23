"""
Security Integration Module

Provides unified access to all security features:
- Enhanced authentication with remember me
- File upload validation
- Rate limiting
- Session management
- Input validation
- Security scanning

This module makes it easy to use all security features consistently.
"""

import logging
from typing import Optional, Dict, Any
from pathlib import Path

logger = logging.getLogger(__name__)

# ============================================================================
# Authentication & Session Management
# ============================================================================

try:
    from education_system.post_18.university_system.infrastructure.auth.enhanced_auth import (
        EnhancedAuth,
        create_enhanced_auth
    )
    ENHANCED_AUTH_AVAILABLE = True
except ImportError as e:
    logger.warning(f"Enhanced authentication not available: {e}")
    ENHANCED_AUTH_AVAILABLE = False
    EnhancedAuth = None
    create_enhanced_auth = None

try:
    from education_system.post_18.university_system.infrastructure.security.remember_me import (
        remember_me_manager,
        RememberMeManager
    )
    REMEMBER_ME_AVAILABLE = True
except ImportError:
    REMEMBER_ME_AVAILABLE = False
    remember_me_manager = None
    RememberMeManager = None

try:
    from education_system.post_18.university_system.infrastructure.security.session_management import (
        SessionManager
    )
    SESSION_MANAGER_AVAILABLE = True
except ImportError:
    SESSION_MANAGER_AVAILABLE = False
    SessionManager = None

# ============================================================================
# Rate Limiting
# ============================================================================

try:
    from education_system.post_18.university_system.infrastructure.security.rate_limiter import (
        login_limiter,
        api_limiter,
        password_reset_limiter,
        RateLimiter,
        RateLimitExceeded
    )
    RATE_LIMITER_AVAILABLE = True
except ImportError:
    RATE_LIMITER_AVAILABLE = False
    login_limiter = None
    api_limiter = None
    password_reset_limiter = None
    RateLimiter = None
    RateLimitExceeded = None

# ============================================================================
# File Upload Security
# ============================================================================

try:
    from education_system.post_18.university_system.infrastructure.security.file_upload_validator import (
        FileUploadValidator,
        document_validator,
        image_validator,
        avatar_validator,
        strict_validator,
        UploadValidationResult
    )
    FILE_UPLOAD_VALIDATOR_AVAILABLE = True
except ImportError:
    FILE_UPLOAD_VALIDATOR_AVAILABLE = False
    FileUploadValidator = None
    document_validator = None
    image_validator = None
    avatar_validator = None
    strict_validator = None
    UploadValidationResult = None

try:
    from education_system.post_18.university_system.infrastructure.security.file_upload import (
        get_upload_handler,
        SecureFileUploadHandler
    )
    FILE_UPLOAD_HANDLER_AVAILABLE = True
except ImportError:
    FILE_UPLOAD_HANDLER_AVAILABLE = False
    get_upload_handler = None
    SecureFileUploadHandler = None

# ============================================================================
# Input Validation
# ============================================================================

try:
    from education_system.post_18.university_system.modules.shared.utils.input_validation import (
        InputValidator,
        ValidationError,
        validate_email,
        validate_phone,
        validate_date,
        validate_numeric,
        validate_student_id,
        validate_username,
        is_valid_email,
        is_valid_phone
    )
    INPUT_VALIDATOR_AVAILABLE = True
except ImportError:
    INPUT_VALIDATOR_AVAILABLE = False
    InputValidator = None
    ValidationError = None

# ============================================================================
# Security Integration Class
# ============================================================================

class SecurityManager:
    """
    Unified security manager providing access to all security features.

    This class provides a single interface to all security components,
    making it easy to implement consistent security across the application.

    Usage:
        from education_system.post_18.university_system.infrastructure.security.security_integration import SecurityManager

        # Initialize security manager
        security = SecurityManager()

        # Enhanced authentication with remember me
        auth_result = security.login_with_remember_me(
            username='user',
            password='pass',
            remember_me=True,
            device_fingerprint='device123',
            ip_address='192.168.1.1'
        )

        # Validate file upload
        # (use paths.TEMP_DIR / 'upload.pdf' in real code)
        file_result = security.validate_file_upload(
            file_path='<temp-upload-path>',
            original_filename='document.pdf',
            validator_type='document'
        )

        # Check rate limit
        if security.check_rate_limit('user@example.com', 'login'):
            # Proceed with action
            pass
    """

    def __init__(self):
        """Initialize security manager with available components"""
        self.auth = create_enhanced_auth() if ENHANCED_AUTH_AVAILABLE else None
        self.remember_me = remember_me_manager if REMEMBER_ME_AVAILABLE else None
        self.session_manager = SessionManager() if SESSION_MANAGER_AVAILABLE else None

        # File validators
        self.document_validator = document_validator if FILE_UPLOAD_VALIDATOR_AVAILABLE else None
        self.image_validator = image_validator if FILE_UPLOAD_VALIDATOR_AVAILABLE else None
        self.avatar_validator = avatar_validator if FILE_UPLOAD_VALIDATOR_AVAILABLE else None
        self.strict_validator = strict_validator if FILE_UPLOAD_VALIDATOR_AVAILABLE else None

        # Rate limiters
        self.login_limiter = login_limiter if RATE_LIMITER_AVAILABLE else None
        self.api_limiter = api_limiter if RATE_LIMITER_AVAILABLE else None
        self.password_reset_limiter = password_reset_limiter if RATE_LIMITER_AVAILABLE else None

        # Input validator
        self.input_validator = InputValidator if INPUT_VALIDATOR_AVAILABLE else None

    def login_with_remember_me(
        self,
        username: str,
        password: str,
        remember_me: bool = False,
        device_fingerprint: Optional[str] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None
    ) -> Dict:
        """
        Login with remember me support.

        Args:
            username: Username
            password: Password
            remember_me: Create persistent token
            device_fingerprint: Device identifier
            ip_address: Client IP
            user_agent: Browser user agent

        Returns:
            Login result dictionary
        """
        if not self.auth:
            return {'success': False, 'error': 'Enhanced authentication not available'}

        return self.auth.login_with_remember_me(
            username=username,
            password=password,
            remember_me=remember_me,
            device_fingerprint=device_fingerprint,
            ip_address=ip_address,
            user_agent=user_agent
        )

    def validate_file_upload(
        self,
        file_path: str,
        original_filename: Optional[str] = None,
        validator_type: str = 'document'
    ) -> Dict:
        """
        Validate uploaded file.

        Args:
            file_path: Path to uploaded file
            original_filename: Original filename
            validator_type: Type of validator ('document', 'image', 'avatar', 'strict')

        Returns:
            Validation result dictionary
        """
        if not FILE_UPLOAD_VALIDATOR_AVAILABLE:
            return {'valid': False, 'error': 'File upload validator not available'}

        # Select validator
        validators = {
            'document': self.document_validator,
            'image': self.image_validator,
            'avatar': self.avatar_validator,
            'strict': self.strict_validator
        }

        validator = validators.get(validator_type, self.document_validator)
        if not validator:
            return {'valid': False, 'error': f'Validator type {validator_type} not available'}

        # Validate file
        result = validator.validate_file(file_path, original_filename)

        return {
            'valid': result.valid,
            'error': result.error,
            'warnings': result.warnings,
            'sanitized_filename': result.sanitized_filename,
            'file_hash': result.file_hash,
            'mime_type': result.mime_type
        }

    def check_rate_limit(
        self,
        identifier: str,
        limiter_type: str = 'login'
    ) -> bool:
        """
        Check if action is rate limited.

        Args:
            identifier: Unique identifier (username, IP, etc.)
            limiter_type: Type of limiter ('login', 'api', 'password_reset')

        Returns:
            True if allowed, False if rate limited
        """
        if not RATE_LIMITER_AVAILABLE:
            # Fail closed: without a rate limiter we cannot enforce brute-force
            # protection, so deny rather than silently allowing unlimited
            # attempts.
            logger.critical(
                "Rate limiter unavailable; denying '%s' action for '%s' "
                "(fail-closed).",
                limiter_type,
                identifier,
            )
            return False

        limiters = {
            'login': self.login_limiter,
            'api': self.api_limiter,
            'password_reset': self.password_reset_limiter
        }

        limiter = limiters.get(limiter_type, self.login_limiter)
        if not limiter:
            logger.critical(
                "Rate limiter '%s' not configured; denying action for '%s' "
                "(fail-closed).",
                limiter_type,
                identifier,
            )
            return False

        return limiter.is_allowed(identifier)

    def validate_input(
        self,
        value: str,
        field_type: str,
        **kwargs
    ) -> Dict:
        """
        Validate user input.

        Args:
            value: Input value
            field_type: Type of field (email, phone, username, etc.)
            **kwargs: Additional validation parameters

        Returns:
            Validation result dictionary
        """
        if not self.input_validator:
            return {'valid': False, 'error': 'Input validator not available'}

        return self.input_validator.validate_with_length(
            value,
            field_type,
            **kwargs
        )

    def get_security_status(self) -> Dict[str, bool]:
        """
        Get status of all security components.

        Returns:
            Dictionary showing which components are available
        """
        return {
            'enhanced_auth': ENHANCED_AUTH_AVAILABLE,
            'remember_me': REMEMBER_ME_AVAILABLE,
            'session_manager': SESSION_MANAGER_AVAILABLE,
            'rate_limiter': RATE_LIMITER_AVAILABLE,
            'file_upload_validator': FILE_UPLOAD_VALIDATOR_AVAILABLE,
            'file_upload_handler': FILE_UPLOAD_HANDLER_AVAILABLE,
            'input_validator': INPUT_VALIDATOR_AVAILABLE
        }

    def get_active_sessions(self, user_id: Optional[int] = None) -> list:
        """
        Get all active sessions for a user.

        Args:
            user_id: User ID (uses current user if not provided)

        Returns:
            List of active sessions
        """
        if not self.auth:
            return []

        return self.auth.get_active_sessions(user_id)

    def revoke_all_sessions(self, user_id: Optional[int] = None):
        """
        Revoke all sessions and remember me tokens for a user.

        Args:
            user_id: User ID (uses current user if not provided)
        """
        if not self.auth:
            return

        self.auth.logout_and_revoke_remember_me(user_id)


# Global security manager instance
_security_manager: Optional[SecurityManager] = None


def get_security_manager() -> SecurityManager:
    """Get the global security manager instance"""
    global _security_manager

    if _security_manager is None:
        _security_manager = SecurityManager()

    return _security_manager


# Convenience functions for quick access
def login_with_security(username: str, password: str, **kwargs) -> Dict:
    """Quick login with all security features"""
    return get_security_manager().login_with_remember_me(username, password, **kwargs)


def validate_upload(file_path: str, **kwargs) -> Dict:
    """Quick file upload validation"""
    return get_security_manager().validate_file_upload(file_path, **kwargs)


def check_rate_limit(identifier: str, limiter_type: str = 'login') -> bool:
    """Quick rate limit check"""
    return get_security_manager().check_rate_limit(identifier, limiter_type)


def validate_input(value: str, field_type: str, **kwargs) -> Dict:
    """Quick input validation"""
    return get_security_manager().validate_input(value, field_type, **kwargs)


# Export all for easy importing
__all__ = [
    'SecurityManager',
    'get_security_manager',
    'login_with_security',
    'validate_upload',
    'check_rate_limit',
    'validate_input',
    # Auth
    'EnhancedAuth',
    'create_enhanced_auth',
    'RememberMeManager',
    'remember_me_manager',
    'SessionManager',
    # Rate Limiting
    'RateLimiter',
    'RateLimitExceeded',
    'login_limiter',
    'api_limiter',
    'password_reset_limiter',
    # File Upload
    'FileUploadValidator',
    'UploadValidationResult',
    'document_validator',
    'image_validator',
    'avatar_validator',
    'strict_validator',
    # Input Validation
    'InputValidator',
    'ValidationError',
    'validate_email',
    'validate_phone',
    # Feature flags
    'ENHANCED_AUTH_AVAILABLE',
    'REMEMBER_ME_AVAILABLE',
    'RATE_LIMITER_AVAILABLE',
    'FILE_UPLOAD_VALIDATOR_AVAILABLE',
    'INPUT_VALIDATOR_AVAILABLE',
]
