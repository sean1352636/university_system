"""
Authentication Managers Module

This module contains all manager classes and modules for the authentication system.
Each manager handles a specific concern of the authentication system.

Managers (Classes)
------------------
- DatabaseConnectionManager: Thread-safe database connections
- LoginManager: Login and logout operations
- SessionManager: Session tracking and timeout
- UserManager: User CRUD operations
- PermissionManager: Permission checking
- RoleManager: Role management
- MFAManager: Multi-factor authentication
- AccountSecurityManager: Account lockout and security
- SSOManager: Single Sign-On provider management
- WebAuthnManager: WebAuthn/FIDO2 credential management
- BiometricManager: Biometric authentication enrollment and verification
- DelegatedAccessManager: Delegated access and power of attorney management

Managers (Function Modules)
----------------------------
- password_manager: Password hashing and validation functions
- activity_logger: Audit trail logging functions
"""

# Import manager classes
from education_system.post_18.university_system.infrastructure.auth.managers.database_manager import DatabaseConnectionManager
from education_system.post_18.university_system.infrastructure.auth.managers.login_manager import LoginManager
from education_system.post_18.university_system.infrastructure.auth.managers.session_manager import SessionManager
from education_system.post_18.university_system.infrastructure.auth.managers.user_manager import UserManager
from education_system.post_18.university_system.infrastructure.auth.managers.permission_manager import PermissionManager
from education_system.post_18.university_system.infrastructure.auth.managers.role_manager import RoleManager
from education_system.post_18.university_system.infrastructure.auth.managers.mfa_manager import MFAManager
from education_system.post_18.university_system.infrastructure.auth.managers.account_security import AccountSecurityManager
from education_system.post_18.university_system.infrastructure.auth.managers.sso_manager import SSOManager
from education_system.post_18.university_system.infrastructure.auth.managers.webauthn_manager import WebAuthnManager
from education_system.post_18.university_system.infrastructure.auth.managers.biometric_manager import BiometricManager
from education_system.post_18.university_system.infrastructure.auth.managers.delegated_access_manager import DelegatedAccessManager

# Import function-based managers as modules
from education_system.post_18.university_system.infrastructure.auth.managers import password_manager
from education_system.post_18.university_system.infrastructure.auth.managers import activity_logger

__all__ = [
    # Manager classes
    'DatabaseConnectionManager',
    'LoginManager',
    'SessionManager',
    'UserManager',
    'PermissionManager',
    'RoleManager',
    'MFAManager',
    'AccountSecurityManager',
    'SSOManager',
    'WebAuthnManager',
    'BiometricManager',
    'DelegatedAccessManager',

    # Function-based modules
    'password_manager',
    'activity_logger',
]
