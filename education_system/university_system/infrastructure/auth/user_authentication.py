"""
User Authentication Module

Backward-compatible module that re-exports the UserAuth class from core.py.
This module exists so that code and tests can reference:
    education_system.university_system.infrastructure.auth.user_authentication.UserAuth
"""

from education_system.university_system.infrastructure.auth.core import UserAuth

__all__ = ['UserAuth']
