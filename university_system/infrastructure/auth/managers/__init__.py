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

Managers (Function Modules)
----------------------------
- password_manager: Password hashing and validation functions
- activity_logger: Audit trail logging functions
"""

# Import manager classes
from .database_manager import DatabaseConnectionManager
from .login_manager import LoginManager
from .session_manager import SessionManager
from .user_manager import UserManager
from .permission_manager import PermissionManager
from .role_manager import RoleManager
from .mfa_manager import MFAManager
from .account_security import AccountSecurityManager

# Import function-based managers as modules
from . import password_manager
from . import activity_logger

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

    # Function-based modules
    'password_manager',
    'activity_logger',
]
