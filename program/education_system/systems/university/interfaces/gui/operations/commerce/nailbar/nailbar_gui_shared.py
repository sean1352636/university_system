"""Shared imports and module state for the split implementation."""

import tkinter as tk

from tkinter import ttk, messagebox

import logging

from datetime import datetime, timedelta

from typing import Optional, List

from education_system.systems.university.infrastructure.i18n import get_text as _t

from education_system.systems.university.infrastructure.database.db import get_db_connection, transaction

from education_system.systems.university.infrastructure.activity_logger import log_activity

try:
    from education_system.systems.university.infrastructure.shared_context import get_auth, _DummyAuth
    AUTH_AVAILABLE = True
except ImportError:
    AUTH_AVAILABLE = False
    get_auth = None
    _DummyAuth = None

try:
    from education_system.systems.university.infrastructure.utils.finance_integration import (
        record_payment_to_finance,
        get_student_finance_account_balance,
        process_student_finance_account_payment,
        ensure_student_finance_account_exists
    )
    FINANCE_AVAILABLE = True
except ImportError:
    FINANCE_AVAILABLE = False
    record_payment_to_finance = None

try:
    from education_system.systems.university.infrastructure.email.email_service import send_email
    EMAIL_AVAILABLE = True
except ImportError:
    EMAIL_AVAILABLE = False
    send_email = None

logger = logging.getLogger(__name__)

__all__ = [name for name in globals() if not name.startswith("__") and name != "__all__"]
