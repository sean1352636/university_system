"""Shared imports and module state for the split implementation."""

import tkinter as tk

from tkinter import ttk, messagebox, filedialog

from education_system.systems.university.infrastructure.database.db import sqlite3

from datetime import datetime

import random

import string

from pathlib import Path

import logging

from education_system import paths

from education_system.systems.university.infrastructure.database.db import get_db_connection

from education_system.systems.university.infrastructure.i18n import (
    init_i18n,
    get_text as _t,
    get_current_language,
)

from education_system.systems.university.infrastructure.shared_context import get_auth, get_current_user

try:
    from education_system.systems.university.infrastructure.email.email_service import send_email
    EMAIL_AVAILABLE = True
except ImportError:
    EMAIL_AVAILABLE = False

try:
    from education_system.systems.university.infrastructure.email.template_utils import render_template
    TEMPLATE_AVAILABLE = True
except ImportError:
    TEMPLATE_AVAILABLE = False

try:
    from education_system.systems.university.domains.finance.infrastructure.finance_integration import (
        get_student_finance_account_balance,
        process_student_finance_account_payment,
        get_student_info,
        get_student_email,
    )
    FINANCE_AVAILABLE = True
except ImportError:
    FINANCE_AVAILABLE = False

logger = logging.getLogger(__name__)

__all__ = [name for name in globals() if not name.startswith("__") and name != "__all__"]
