import logging
from datetime import datetime, timedelta
from functools import wraps
from education_system.university_system.utils.logging.log_config import configure_logging
from education_system.university_system.modules.domain.academics.services.academic_calendar.exceptions import ValidationError, PermissionError
from education_system.university_system.modules.domain.academics.services.academic_calendar.config import ValidationUtils, SecurityUtils

logger = configure_logging(name=__name__)


# Authentication and Authorization
class AuthenticationManager:
    def __init__(self, db_manager):
        self.db_manager = db_manager
        self.current_user = None
        self.permissions_cache = {}
        self.session_token = None
        self.session_expires = None
        # Don't try to create our own user system - use the existing one

    # authenticate_user() removed - use infrastructure.auth.user_authentication.UserAuth instead

    def check_permission(self, permission: str) -> bool:
        """Check if current user has specific permission using main auth system"""
        # Get the global auth instance
        from education_system.university_system.infrastructure.auth import _current_auth_instance
        if _current_auth_instance and _current_auth_instance.current_user:
            return _current_auth_instance.check_permission(permission)
        return False

    def _load_permissions(self):
        """Load permissions from main auth system"""
        from education_system.university_system.infrastructure.auth import _current_auth_instance
        if _current_auth_instance and _current_auth_instance.current_user:
            self.current_user = _current_auth_instance.current_user
            self.permissions_cache = set(_current_auth_instance.current_user.get('permissions', []))

    def _create_session(self):
        """Create user session"""
        self.session_token = SecurityUtils.generate_token()
        self.session_expires = datetime.now() + timedelta(seconds=3600)  # 1 hour

    def check_permission(self, permission: str) -> bool:
        """Check if current user has specific permission"""
        if not self.current_user or not self._is_session_valid():
            return False
        return permission in self.permissions_cache

    def _is_session_valid(self) -> bool:
        """Check if current session is valid"""
        if not self.session_expires:
            return False
        return datetime.now() < self.session_expires

    def require_permission(self, permission: str):
        """Decorator to require specific permission"""
        def decorator(func):
            @wraps(func)
            def wrapper(*args, **kwargs):
                if not self.check_permission(permission):
                    raise PermissionError(f"Required permission: {permission}")
                return func(*args, **kwargs)
            return wrapper
        return decorator

    # logout() removed - use infrastructure.auth.user_authentication.UserAuth.logout() instead

    def create_user(self, username: str, password: str, email: str, role: str = 'student') -> bool:
        """Create new user with secure password hashing"""
        try:
            if not all([username, password, email]):
                raise ValidationError("Username, password, and email are required")

            if not ValidationUtils.validate_email(email):
                raise ValidationError("Invalid email format")

            username = ValidationUtils.sanitize_string(username, 50)
            email = ValidationUtils.sanitize_string(email, 100)

            # Check if user already exists
            existing = self.db_manager.execute_query(
                "SELECT id FROM users WHERE username = ? OR email = ?",
                (username, email)
            )
            if existing:
                raise ValidationError("Username or email already exists")

            # Use centralized authentication system
            from education_system.university_system.infrastructure.auth import UserAuthentication

            auth_system = UserAuthentication()
            success = auth_system.register_user(
                username=username,
                password=password,
                email=email,
                role=role
            )

            if success:
                logger.info(f"User {username} created successfully via centralized auth system")
                return True
            else:
                raise ValidationError("User creation failed")

            return True

        except Exception as e:
            logger.error(f"User creation failed: {e}")
            raise
