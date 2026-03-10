"""Unified authentication module for all Education System subsystems."""

from education_system.shared.auth.core import UserAuth
from education_system.shared.auth.password_manager import (
    hash_password,
    verify_password,
    validate_password_strength,
)
from education_system.shared.auth.session_manager import SessionManager
from education_system.shared.auth.role_manager import RoleManager
from education_system.shared.auth.mfa_service import MFAService

__all__ = [
    "UserAuth",
    "hash_password",
    "verify_password",
    "validate_password_strength",
    "SessionManager",
    "RoleManager",
    "MFAService",
]
