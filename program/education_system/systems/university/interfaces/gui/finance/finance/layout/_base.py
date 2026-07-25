"""LayoutManager class definition and module-level setup.

All original module-level imports, constants, and stub definitions are
preserved here so that the rest of the application continues to work
exactly as before.
"""

from education_system.systems.university.infrastructure.database.db import DEFAULT_DB_PATH  # injected
import tkinter as tk
from tkinter import ttk, messagebox, simpledialog, filedialog
from tkinter.scrolledtext import ScrolledText
from education_system.systems.university.infrastructure.database.db import sqlite3
import sys
import io
import os
import csv
import numpy as np
from datetime import datetime, timedelta
import json
import threading
import warnings
from pathlib import Path
from sklearn.ensemble import IsolationForest
from sklearn.preprocessing import StandardScaler
import joblib
from cryptography.fernet import Fernet
import logging
from io import BytesIO
import base64
from education_system.systems.university.interfaces.gui.finance.finance_reporting import launch_financial_gui
from education_system.systems.university.infrastructure.i18n import get_text as _

# Import Research & Grants GUI
try:
    from education_system.systems.university.interfaces.gui.academics.research.research_grants_gui import launch_research_grants_gui
    RESEARCH_GRANTS_AVAILABLE = True
except ImportError:
    RESEARCH_GRANTS_AVAILABLE = False
    launch_research_grants_gui = None

# Import Financial Aid & Scholarships GUI
try:
    from education_system.systems.university.interfaces.gui.finance.financial_aid.financial_aid_gui import launch_financial_aid_gui
    FINANCIAL_AID_GUI_AVAILABLE = True
except ImportError:
    FINANCIAL_AID_GUI_AVAILABLE = False
    launch_financial_aid_gui = None

# Import authentication - REQUIRED (no fallback for security)
from education_system.systems.university.infrastructure.auth import UserAuth, get_global_auth
from education_system.systems.university.infrastructure.shared_context import get_auth

# Import other modules with backward compatibility fallbacks
try:
    from education_system.systems.university.infrastructure.email.email_service import send_email
    from education_system.systems.university.infrastructure.database.db import get_connection, transaction
    from education_system.systems.university.infrastructure.logging.log_config import configure_logging, get_log_file
except ImportError:
    # Fallback for backward compatibility (non-security critical)
    def send_email(*args, **kwargs):
        return True

    from pathlib import Path
    def get_connection():
        """
        Fallback database connection for standalone mode.
        Use the central student_records.db located in the refactored/db_files
        directory rather than creating an enhanced_student_finance.db in the
        current working directory. This ensures the application operates on
        a single database file when the main refactored modules are not
        available.
        """
        return sqlite3.connect(str(DEFAULT_DB_PATH))

    def configure_logging(name=None):
        return logging.getLogger(name or __name__)

    def get_log_file(name):
        from education_system.systems.university.infrastructure import paths
        return str(paths.LOG_DIR / name)

try:
    from education_system.systems.university.domain.finance.core.financial_core import (
        assign_to_collection_agency, track_collection_progress,
        update_collection_case_status, create_payment_arrangement,
        send_arrangement_confirmation, setup_collection_workflows,
        check_required_packages, ensure_database_exists, verify_fix
    )
except ImportError:
    # Stub implementations for missing functions
    def assign_to_collection_agency(*args, **kwargs):
        print("assign_to_collection_agency function not implemented")

    def track_collection_progress(*args, **kwargs):
        print("track_collection_progress function not implemented")

    def update_collection_case_status(*args, **kwargs):
        print("update_collection_case_status function not implemented")

    def create_payment_arrangement(*args, **kwargs):
        print("create_payment_arrangement function not implemented")

    def send_arrangement_confirmation(*args, **kwargs):
        print("send_arrangement_confirmation function not implemented")

    def setup_collection_workflows(*args, **kwargs):
        print("setup_collection_workflows function not implemented")

    def check_required_packages(*args, **kwargs):
        print("check_required_packages function not implemented")

    def ensure_database_exists(*args, **kwargs):
        print("ensure_database_exists function not implemented")

    def verify_fix(*args, **kwargs):
        print("verify_fix function not implemented")

# Add these import stubs for the missing functions if they don't exist
try:
    from education_system.systems.university.domain.finance.core.financial_core import (
        modify_payment_plan, view_student_credits, add_student_credit,
        manage_financial_aid, create_budget_plan, view_overdue_accounts,
        create_collection_case, aging_analysis_report, collection_case_status_report,
        view_student_collection_detail, manage_collection_agencies,
        budget_vs_actual_analysis, generate_aid_reports, aid_distribution_summary,
        aid_by_academic_year, loan_repayment_status_report, aid_effectiveness_analysis,
        track_loan_repayments, view_aid_types, create_aid_type, edit_aid_type,
        deactivate_aid_type, review_pending_aid_applications, process_loan_payment,
        view_aid_application_detail, manage_budget_categories, view_budget_categories,
        create_budget_category, edit_budget_category, deactivate_budget_category,
        variance_analysis_report, budget_performance_trends, category_performance_report,
        collection_performance_summary, monthly_revenue_trend_report,
        enhanced_notification_system, manage_aid_types, recovery_rate_analysis,
        agency_performance_report, export_forecast_report, complete_database_fix,
        quick_fix_database, initialize_finance, detect_payment_fraud,
        setup_email_config, setup_sms_config, generate_qr_payment_code,
        process_stripe_payment, create_approval_workflow, apply_credit_to_fees,
        update_actual_amounts, view_credit_history, send_collection_notice,
        add_collection_agency, edit_collection_agency, deactivate_collection_agency,
        view_collection_agencies, test_email_service, test_sms_service,
        generate_audit_report
    )
except ImportError:
    # Create stub functions for missing finance core features so the GUI can still load
    def _make_stub(name):
        def _stub(*args, **kwargs):
            print(f"{name} function not implemented")
        return _stub

    _missing_functions = [
        'modify_payment_plan', 'view_student_credits', 'add_student_credit',
        'manage_financial_aid', 'create_budget_plan', 'view_overdue_accounts',
        'create_collection_case', 'aging_analysis_report', 'collection_case_status_report',
        'view_student_collection_detail', 'manage_collection_agencies',
        'budget_vs_actual_analysis', 'generate_aid_reports', 'aid_distribution_summary',
        'aid_by_academic_year', 'loan_repayment_status_report', 'aid_effectiveness_analysis',
        'track_loan_repayments', 'view_aid_types', 'create_aid_type', 'edit_aid_type',
        'deactivate_aid_type', 'review_pending_aid_applications', 'process_loan_payment',
        'view_aid_application_detail', 'manage_budget_categories', 'view_budget_categories',
        'create_budget_category', 'edit_budget_category', 'deactivate_budget_category',
        'variance_analysis_report', 'budget_performance_trends', 'category_performance_report',
        'collection_performance_summary', 'monthly_revenue_trend_report',
        'enhanced_notification_system', 'manage_aid_types', 'recovery_rate_analysis',
        'agency_performance_report', 'export_forecast_report', 'complete_database_fix',
        'quick_fix_database', 'initialize_finance', 'detect_payment_fraud',
        'setup_email_config', 'setup_sms_config', 'generate_qr_payment_code',
        'process_stripe_payment', 'create_approval_workflow', 'apply_credit_to_fees',
        'update_actual_amounts', 'view_credit_history', 'send_collection_notice',
        'add_collection_agency', 'edit_collection_agency', 'deactivate_collection_agency',
        'view_collection_agencies', 'test_email_service', 'test_sms_service',
        'generate_audit_report'
    ]

    globals().update({name: _make_stub(name) for name in _missing_functions})

# Configure logging
log_path = get_log_file("app.log")
os.makedirs(os.path.dirname(log_path), exist_ok=True)


logger = configure_logging(name=__name__)
warnings.filterwarnings('ignore')

# Global variables for backward compatibility
auth = get_global_auth()  # Use centralized auth instance
ENCRYPTION_KEY = Fernet.generate_key()
cipher_suite = Fernet(ENCRYPTION_KEY)

# Payment gateway configurations (from original file)
PAYMENT_GATEWAYS = {
    'stripe': {
        'public_key': os.getenv('STRIPE_PUBLIC_KEY', ''),
        'secret_key': os.getenv('STRIPE_SECRET_KEY', ''),
        'webhook_secret': os.getenv('STRIPE_WEBHOOK_SECRET', '')
    },
    'paypal': {
        'client_id': os.getenv('PAYPAL_CLIENT_ID', ''),
        'client_secret': os.getenv('PAYPAL_CLIENT_SECRET', ''),
        'environment': os.getenv('PAYPAL_ENVIRONMENT', 'sandbox')
    }
}

# WARNING: Never commit real API keys to version control!
# Set these environment variables in your deployment environment
SUPPORTED_CURRENCIES = ['GBP', 'USD', 'EUR', 'CAD', 'AUD']
# Load exchange API key from environment variable
EXCHANGE_API_KEY = os.getenv('EXCHANGE_API_KEY', '')


# ---------------------------------------------------------------------------
# Import all mixin classes
# ---------------------------------------------------------------------------
from education_system.systems.university.interfaces.gui.finance.finance.layout._styles import StylesMixin
from education_system.systems.university.interfaces.gui.finance.finance.layout._navigation import NavigationMixin
from education_system.systems.university.interfaces.gui.finance.finance.layout._dashboard import DashboardMixin
from education_system.systems.university.interfaces.gui.finance.finance.layout._core_finance import CoreFinanceMixin
from education_system.systems.university.interfaces.gui.finance.finance.layout._refunds import RefundsMixin
from education_system.systems.university.interfaces.gui.finance.finance.layout._payments import PaymentsMixin
from education_system.systems.university.interfaces.gui.finance.finance.layout._payment_plans import PaymentPlansMixin
from education_system.systems.university.interfaces.gui.finance.finance.layout._fees import FeesMixin
from education_system.systems.university.interfaces.gui.finance.finance.layout._late_fees import LateFeesMixin
from education_system.systems.university.interfaces.gui.finance.finance.layout._students import StudentsMixin
from education_system.systems.university.interfaces.gui.finance.finance.layout._currency import CurrencyMixin
from education_system.systems.university.interfaces.gui.finance.finance.layout._analytics import AnalyticsMixin
from education_system.systems.university.interfaces.gui.finance.finance.layout._scholarships import ScholarshipsMixin
from education_system.systems.university.interfaces.gui.finance.finance.layout._reports import ReportsMixin
from education_system.systems.university.interfaces.gui.finance.finance.layout._revenue import RevenueMixin
from education_system.systems.university.interfaces.gui.finance.finance.layout._collections import CollectionsMixin
from education_system.systems.university.interfaces.gui.finance.finance.layout._financial_aid import FinancialAidMixin
from education_system.systems.university.interfaces.gui.finance.finance.layout._budget import BudgetMixin
from education_system.systems.university.interfaces.gui.finance.finance.layout._forecasting import ForecastingMixin
from education_system.systems.university.interfaces.gui.finance.finance.layout._admin import AdminMixin
from education_system.systems.university.interfaces.gui.finance.finance.layout._research_grants import ResearchGrantsMixin
from education_system.systems.university.interfaces.gui.finance.finance.layout._bank_app import BankAppMixin
from education_system.systems.university.interfaces.gui.finance.finance.layout._club_payments import ClubPaymentsMixin
from education_system.systems.university.interfaces.gui.finance.finance.layout._settings import SettingsMixin
from education_system.systems.university.interfaces.gui.finance.finance.layout._status_bar import StatusBarMixin
from education_system.systems.university.interfaces.gui.finance.finance.layout._ledger import LedgerMixin
from education_system.systems.university.interfaces.gui.finance.finance.layout._bank_rec import BankRecMixin
from education_system.systems.university.interfaces.gui.finance.finance.layout._statements import StatementsMixin


class LayoutManager(
    StylesMixin,
    NavigationMixin,
    DashboardMixin,
    CoreFinanceMixin,
    RefundsMixin,
    PaymentsMixin,
    PaymentPlansMixin,
    FeesMixin,
    LateFeesMixin,
    StudentsMixin,
    CurrencyMixin,
    AnalyticsMixin,
    ScholarshipsMixin,
    ReportsMixin,
    RevenueMixin,
    CollectionsMixin,
    FinancialAidMixin,
    BudgetMixin,
    ForecastingMixin,
    AdminMixin,
    ResearchGrantsMixin,
    BankAppMixin,
    ClubPaymentsMixin,
    SettingsMixin,
    StatusBarMixin,
    LedgerMixin,
    BankRecMixin,
    StatementsMixin,
):
    """UI layout and navigation"""

    def __init__(self, gui):
        """Initialize manager with reference to main GUI"""
        self.gui = gui
        self.root = gui.root
        self.conn = gui.conn
        try:
            self.finance_system = gui.finance_system
        except Exception:
            self.finance_system = None
