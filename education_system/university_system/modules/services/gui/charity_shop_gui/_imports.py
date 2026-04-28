#!/usr/bin/env python3
"""
Charity Shop Stock Management System - Shared Imports
All shared imports, constants, and utility functions used across the package.
"""

from education_system.university_system.infrastructure.database.db import sqlite3
from education_system.university_system.core.sql_safety import validate_table_name
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
from tkinter.scrolledtext import ScrolledText
from datetime import datetime, timedelta
from pathlib import Path
import logging
import json
import os

# University system imports
from education_system.university_system.modules.shared.constants.paths import DEFAULT_DB_PATH
from education_system.university_system.infrastructure.shared_context import get_auth, get_current_user
from education_system.university_system.core.sql_safety import safe_alter_table_add_column

# Import activity logger for audit trail
try:
    from education_system.university_system.modules.shared.utils.activity_logger import log_activity
    ACTIVITY_LOGGER_AVAILABLE = True
except ImportError:
    ACTIVITY_LOGGER_AVAILABLE = False
    log_activity = lambda *args, **kwargs: None

# Import i18n for language support
from education_system.university_system.modules.shared.utils.i18n import (
    init_i18n,
    get_text as _t,
    get_current_language,
)
from education_system.university_system.modules.shared.utils.gui_language_selector import (
    show_gui_language_selector,
    create_language_menu_button,
)

# Import finance integration for revenue tracking and student payments
try:
    from education_system.university_system.modules.shared.utils.finance_integration import (
        record_revenue_to_finance,
        process_student_finance_account_payment,
        get_student_finance_account_balance,
        get_student_info,
        get_student_email,
    )
    FINANCE_INTEGRATION_AVAILABLE = True
except ImportError:
    FINANCE_INTEGRATION_AVAILABLE = False
    record_revenue_to_finance = lambda *args, **kwargs: None
    process_student_finance_account_payment = lambda *args, **kwargs: {'success': False, 'message': 'Finance integration not available'}
    get_student_finance_account_balance = lambda x: None
    get_student_info = lambda x: None
    get_student_email = lambda x: None

# Import email service for receipts
try:
    from education_system.university_system.infrastructure.email.email_service import send_email
    EMAIL_SERVICE_AVAILABLE = True
except ImportError:
    EMAIL_SERVICE_AVAILABLE = False
    send_email = lambda *args, **kwargs: False

logger = logging.getLogger(__name__)

# Email templates directory
EMAIL_TEMPLATES_DIR = Path(__file__).parent.parent.parent.parent.parent / "templates" / "email"

# Try to import matplotlib for charts
try:
    import matplotlib.pyplot as plt
    from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
    from matplotlib.figure import Figure
    MATPLOTLIB_AVAILABLE = True
except ImportError:
    MATPLOTLIB_AVAILABLE = False
    plt = None
    FigureCanvasTkAgg = None
    Figure = None
    logger.warning("matplotlib not installed. Charts will be disabled.")


def load_email_template(template_name: str) -> dict:
    """
    Load an email template from JSON file.

    Args:
        template_name: Name of the template file (without .json extension)

    Returns:
        Dictionary with 'subject' and 'body' keys, or empty dict if not found
    """
    try:
        template_path = EMAIL_TEMPLATES_DIR / f"{template_name}.json"
        if template_path.exists():
            with open(template_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        else:
            logger.warning(f"Email template not found: {template_path}")
            return {}
    except Exception as e:
        logger.error(f"Error loading email template {template_name}: {e}")
        return {}


def render_email_template(template: dict, variables: dict) -> tuple:
    """
    Render an email template by replacing variables.

    Args:
        template: Dictionary with 'subject' and 'body' keys
        variables: Dictionary of variable names and values to substitute

    Returns:
        Tuple of (subject, body) with variables replaced
    """
    if not template:
        return "", ""

    subject = template.get('subject', '')
    body = template.get('body', '')

    # Replace variables (using $variable_name format)
    for key, value in variables.items():
        subject = subject.replace(f'£{key}', str(value))
        body = body.replace(f'£{key}', str(value))

    return subject, body
