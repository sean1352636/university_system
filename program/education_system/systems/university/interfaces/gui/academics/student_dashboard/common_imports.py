"""
Common imports and utilities for Student Dashboard GUI

This module provides shared dependencies and utility functions used across
all student dashboard components.
"""

# Standard library imports
import tkinter as tk
from tkinter import ttk, messagebox
from datetime import datetime
import logging
from typing import Optional

# Database
from education_system.systems.university.infrastructure.database.db import get_connection

# Authentication
from education_system.systems.university.infrastructure.shared_context import get_auth

# i18n
try:
    from education_system.systems.university.infrastructure.i18n import get_text as _t
except ImportError:
    def _t(key, default=""):
        return default or key

# Logger
logger = logging.getLogger(__name__)

# Color scheme
COLORS = {
    'primary': '#2c3e50',
    'secondary': '#34495e',
    'success': '#27ae60',
    'warning': '#f39c12',
    'danger': '#e74c3c',
    'info': '#3498db',
    'light': '#ecf0f1',
    'dark': '#2c3e50',
    'white': '#ffffff',
}


def get_student_id(auth) -> Optional[str]:
    """
    Extract the student ID from the current auth instance.

    Args:
        auth: Authentication instance

    Returns:
        Student ID string or None
    """
    if auth and hasattr(auth, 'current_user') and auth.current_user:
        user = auth.current_user
        if hasattr(user, 'to_dict'):
            user_dict = user.to_dict()
        elif hasattr(user, '__dict__'):
            user_dict = user.__dict__
        elif isinstance(user, dict):
            user_dict = user
        else:
            user_dict = {}

        student_id = (
            user_dict.get('student_id')
            or user_dict.get('user_id')
            or user_dict.get('id')
            or getattr(user, 'student_id', None)
            or getattr(user, 'user_id', None)
            or getattr(user, 'id', None)
        )
        return str(student_id) if student_id else None
    return None


def get_student_name(auth) -> str:
    """
    Extract the student display name from the current auth instance.

    Args:
        auth: Authentication instance

    Returns:
        Student name string or 'Student'
    """
    if auth and hasattr(auth, 'current_user') and auth.current_user:
        user = auth.current_user
        if hasattr(user, 'to_dict'):
            user_dict = user.to_dict()
        elif hasattr(user, '__dict__'):
            user_dict = user.__dict__
        elif isinstance(user, dict):
            user_dict = user
        else:
            user_dict = {}

        name = (
            user_dict.get('full_name')
            or user_dict.get('name')
            or user_dict.get('display_name')
            or getattr(user, 'full_name', None)
            or getattr(user, 'name', None)
            or getattr(user, 'display_name', None)
        )
        if not name:
            first = user_dict.get('first_name') or getattr(user, 'first_name', '')
            last = user_dict.get('last_name') or getattr(user, 'last_name', '')
            if first or last:
                name = f"{first} {last}".strip()
        return name if name else 'Student'
    return 'Student'


def create_stat_card(parent, title: str, value: str, color: str = 'primary') -> ttk.Frame:
    """
    Create a statistics card widget.

    Args:
        parent: Parent widget
        title: Card title
        value: Value to display
        color: Color theme key from COLORS

    Returns:
        Frame containing the card
    """
    card = ttk.Frame(parent, relief='raised', borderwidth=2)

    title_label = ttk.Label(card, text=title, font=('Arial', 10))
    title_label.pack(pady=(10, 5))

    value_label = ttk.Label(
        card, text=value,
        font=('Arial', 18, 'bold'),
        foreground=COLORS.get(color, COLORS['primary']),
    )
    value_label.pack(pady=(0, 10))

    return card


__all__ = [
    # Standard library re-exports
    'tk', 'ttk', 'messagebox',
    'datetime', 'logging',
    'Optional',
    # Database
    'get_connection',
    # Authentication
    'get_auth',
    # i18n
    '_t',
    # Logger
    'logger',
    # Colors
    'COLORS',
    # Helpers
    'create_stat_card', 'get_student_id', 'get_student_name',
]
