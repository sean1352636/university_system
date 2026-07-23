"""
CLI Interface Module

This module contains all CLI menu functions for the authentication system.

Functions
---------
- display_auth_menu: Main authentication menu
- display_user_management_menu: User management interface
- display_role_management_menu: Role management interface
- display_my_account_menu: Account settings menu
- display_mfa_settings_menu: MFA configuration menu
- display_chatbot_integration_menu: Chatbot menu
"""

from education_system.post_18.university_system.infrastructure.auth.cli.cli_menus import (
    display_auth_menu,
    display_user_management_menu,
    display_role_management_menu,
    display_my_account_menu,
    display_mfa_settings_menu,
    display_chatbot_integration_menu,
)

__all__ = [
    'display_auth_menu',
    'display_user_management_menu',
    'display_role_management_menu',
    'display_my_account_menu',
    'display_mfa_settings_menu',
    'display_chatbot_integration_menu',
]
