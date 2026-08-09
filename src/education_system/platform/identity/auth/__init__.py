"""Unified authentication module for all Education System subsystems."""

from education_system.platform.identity.auth.core import UserAuth
from education_system.platform.identity.auth.password_manager import (
    hash_password,
    verify_password,
    validate_password_strength,
)
from education_system.platform.identity.auth.session_manager import SessionManager
from education_system.platform.identity.auth.role_manager import RoleManager
from education_system.platform.identity.auth.mfa_service import MFAService

__all__ = [
    "UserAuth",
    "hash_password",
    "verify_password",
    "validate_password_strength",
    "SessionManager",
    "RoleManager",
    "MFAService",
]
