"""Shared dependencies for the betting shop GUI modules."""

import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext, simpledialog
from datetime import datetime, timedelta
from typing import Optional, List, Dict
import traceback
import random

from education_system.systems.university.infrastructure.database.db import get_connection, transaction
from education_system.systems.university.domain.operations.commerce.betting.services.betting_core import (
    AccountManager, SportsBettingManager, PredictionMarketManager,
    ReportManager, init_betting_db,
    MIN_BET, MAX_BET, MIN_DEPOSIT, MAX_DEPOSIT,
    PREDICTION_CATEGORIES, BET_STATUSES
)
from education_system.systems.university.infrastructure.activity_logger import log_activity

# Import internationalization (i18n)
try:
    from education_system.systems.university.infrastructure.i18n import (
        get_text as _t,
        get_current_language,
    )
    I18N_AVAILABLE = True
except ImportError:
    I18N_AVAILABLE = False
    _t = lambda key, **kwargs: kwargs.get("default", key)
    get_current_language = lambda: "en"

# Import email service
try:
    from education_system.systems.university.infrastructure.email.email_service import send_email
    from education_system.systems.university.infrastructure.email.template_utils import render_template
    EMAIL_AVAILABLE = True
except ImportError:
    EMAIL_AVAILABLE = False
    def send_email(*args, **kwargs):
        print("Email service not available")
        return False
    render_template = None

# Import finance integration
try:
    from education_system.systems.university.domain.finance.core.finance_db_operations import (
        record_payment_to_finance,
        get_student_finance_account_balance,
        process_student_finance_account_payment
    )
    FINANCE_AVAILABLE = True
except ImportError:
    FINANCE_AVAILABLE = False
    def record_payment_to_finance(*args, **kwargs):
        return None
    def get_student_finance_account_balance(*args, **kwargs):
        return 0.0
    def process_student_finance_account_payment(*args, **kwargs):
        return False

import logging
logger = logging.getLogger(__name__)


__all__ = [
    "tk", "ttk", "messagebox", "scrolledtext", "simpledialog",
    "datetime", "timedelta", "Optional", "List", "Dict", "traceback",
    "random", "get_connection", "transaction", "AccountManager",
    "SportsBettingManager", "PredictionMarketManager", "ReportManager",
    "init_betting_db", "MIN_BET", "MAX_BET", "MIN_DEPOSIT",
    "MAX_DEPOSIT", "PREDICTION_CATEGORIES", "BET_STATUSES",
    "log_activity", "_t", "get_current_language", "I18N_AVAILABLE",
    "send_email", "render_template", "EMAIL_AVAILABLE",
    "record_payment_to_finance", "get_student_finance_account_balance",
    "process_student_finance_account_payment", "FINANCE_AVAILABLE",
    "logging", "logger",
]
