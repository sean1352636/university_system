"""Shared imports for the Legal Services GUI modules."""

import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext, filedialog, simpledialog
from datetime import datetime, timedelta
from typing import Optional, List, Dict
import traceback
import os

from education_system.systems.university.infrastructure.database.db import get_connection, transaction
from education_system.systems.university.domain.governance.legal.services.legal_services_core import (
    CaseManager, ConsultationManager, DocumentManager, PaymentManager,
    init_legal_services_db, calculate_service_fee, generate_invoice_text,
    CASE_TYPES, CASE_STATUSES, CONSULTATION_STATUSES, PAYMENT_STATUSES, SERVICE_FEES
)
from education_system.systems.university.infrastructure.activity_logger import log_activity

# Import internationalization (i18n) for multi-language support
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
