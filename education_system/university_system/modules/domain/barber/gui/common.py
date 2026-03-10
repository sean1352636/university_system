"""Barber Shop GUI - Shared imports, constants, and flags.

All mixin modules import from here to avoid circular dependencies
and keep import boilerplate in one place.
"""

import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import logging
import csv
import json
from datetime import datetime, timedelta
from typing import Optional, List, Dict

from education_system.university_system.modules.shared.utils.i18n import get_text as _t
from education_system.university_system.infrastructure.database.db import get_db_connection, transaction
from education_system.university_system.modules.shared.utils.activity_logger import log_activity

# Authentication imports
try:
    from education_system.university_system.infrastructure.shared_context import get_auth, _DummyAuth
    AUTH_AVAILABLE = True
except ImportError:
    AUTH_AVAILABLE = False
    get_auth = None
    _DummyAuth = None

# Finance integration imports
try:
    from education_system.university_system.modules.shared.utils.finance_integration import (
        record_payment_to_finance,
        get_student_finance_account_balance,
        process_student_finance_account_payment,
        ensure_student_finance_account_exists
    )
    FINANCE_AVAILABLE = True
except ImportError:
    FINANCE_AVAILABLE = False
    record_payment_to_finance = None

# Email imports
try:
    from education_system.university_system.infrastructure.email.email_service import send_email
    from education_system.university_system.infrastructure.email.template_utils import render_template
    EMAIL_AVAILABLE = True
except ImportError:
    EMAIL_AVAILABLE = False
    send_email = None
    render_template = None

logger = logging.getLogger(__name__)
