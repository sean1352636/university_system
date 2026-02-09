from university_system.infrastructure.database.db import sqlite3
import os
import csv
import pandas as pd
from university_system.modules.shared.constants.paths import FINANCE_TEMPLATES_DIR
import numpy as np
from datetime import datetime, timedelta
import matplotlib.pyplot as plt
import seaborn as sns
from reportlab.lib.pagesizes import letter, landscape
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, Image, PageBreak
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors
from reportlab.lib.units import inch
from reportlab.graphics.charts.barcharts import VerticalBarChart
from reportlab.graphics.charts.piecharts import Pie
from reportlab.graphics.shapes import Drawing
import json
import hashlib
import hmac
import requests
import smtplib
import ssl
import threading
import schedule
import time
import warnings
from sklearn.ensemble import IsolationForest
from sklearn.preprocessing import StandardScaler
import joblib
from cryptography.fernet import Fernet
import logging
from flask import Flask, request, jsonify
import qrcode
from io import BytesIO
import base64
from university_system.infrastructure.email import send_email
from university_system.infrastructure.auth import UserAuth
from university_system.infrastructure.shared_context import get_auth
from university_system.infrastructure.database.db import get_connection
from university_system.utils.logging.log_config import configure_logging
from university_system.modules.shared.utils.i18n import (
    get_text,
    get_current_language,
)
from university_system.modules.shared.utils.language_selector import (
    display_language_menu_option,
)
from university_system.modules.shared.utils.sql_safety import (
    validate_table_name,
    validate_column_name,
    SQLIdentifierError
)

# Configure logging
logger = configure_logging(name=__name__)
warnings.filterwarnings('ignore')


def warn_if_table_empty(cursor, table_name: str, warning_message: str) -> None:
    """Log a warning when expected reference data is missing."""
    try:
        # Validate table name to prevent SQL injection
        validated_table = validate_table_name(table_name, conn=cursor.connection)
        cursor.execute(f'SELECT COUNT(*) FROM [{validated_table}]')
        result = cursor.fetchone()
        if result and result[0] == 0:
            logger.warning(warning_message)
    except SQLIdentifierError as e:
        logger.error(f"Invalid table name in warn_if_table_empty: {e}")
        raise


def load_json_template(filename: str) -> dict:
    """Load JSON template data from the finance templates directory."""
    filepath = FINANCE_TEMPLATES_DIR / filename
    if filepath.exists():
        with open(filepath, 'r') as f:
            return json.load(f)
    return {}


def seed_table_from_json(cursor, table_name: str, json_file: str, columns_map: dict) -> bool:
    """
    Seed a table from a JSON file if the table is empty.

    Args:
        cursor: Database cursor
        table_name: Name of the database table
        json_file: Name of the JSON file in finance_templates
        columns_map: Dict mapping JSON keys to DB column names

    Returns:
        True if data was seeded, False otherwise
    """
    try:
        # Validate table name to prevent SQL injection
        validated_table = validate_table_name(table_name, conn=cursor.connection)
    except SQLIdentifierError as e:
        logger.error(f"Invalid table name in seed_table_from_json: {e}")
        return False

    cursor.execute(f'SELECT COUNT(*) FROM [{validated_table}]')
    result = cursor.fetchone()

    if result and result[0] > 0:
        return False  # Table already has data

    data = load_json_template(json_file)
    if not data:
        return False

    # Get the data array (use first key that contains a list)
    records = None
    for key, value in data.items():
        if isinstance(value, list):
            records = value
            break

    if not records:
        return False

    now = datetime.now().isoformat()
    today = datetime.now().strftime('%Y-%m-%d')

    for record in records:
        columns = []
        values = []

        for json_key, db_column in columns_map.items():
            if json_key in record:
                columns.append(db_column)
                values.append(record[json_key])

        # Add timestamps
        if 'created_at' in columns_map.values() and 'created_at' not in columns:
            columns.append('created_at')
            values.append(now)
        if 'updated_at' in columns_map.values() and 'updated_at' not in columns:
            columns.append('updated_at')
            values.append(now)
        # Add rate_date for exchange rates if not present
        if 'rate_date' in columns_map.values() and 'rate_date' not in columns:
            columns.append('rate_date')
            values.append(today)

        if columns and values:
            try:
                # Validate all column names to prevent SQL injection
                validated_columns = []
                for col in columns:
                    validated_col = validate_column_name(col, table_name=validated_table, conn=cursor.connection)
                    validated_columns.append(validated_col)

                placeholders = ', '.join(['?' for _ in values])
                col_names = ', '.join([f'[{col}]' for col in validated_columns])
                cursor.execute(f'INSERT INTO [{validated_table}] ({col_names}) VALUES ({placeholders})', values)
            except SQLIdentifierError as e:
                logger.error(f"Invalid column name in seed_table_from_json: {e}")
                continue

    return True


def seed_budget_categories(cursor) -> bool:
    """
    Seed budget_categories table from JSON, handling parent-child relationships.

    Budget categories have a hierarchical structure where some categories
    reference parent categories. This function handles the two-pass insertion:
    1. First pass: Insert categories without parents
    2. Second pass: Insert categories with parents, looking up parent IDs
    """
    cursor.execute('SELECT COUNT(*) FROM budget_categories')
    result = cursor.fetchone()

    if result and result[0] > 0:
        return False  # Table already has data

    data = load_json_template('budget_categories.json')
    if not data or 'budget_categories' not in data:
        warn_if_table_empty(
            cursor, 'budget_categories',
            'Budget categories table is empty. Define your budgeting structure in the finance module.'
        )
        return False

    records = data['budget_categories']
    now = datetime.now().isoformat()

    # First pass: Insert categories without parents
    parent_categories = [r for r in records if r.get('parent_category_id') is None and 'parent_category_name' not in r]
    for record in parent_categories:
        cursor.execute(
            '''INSERT INTO budget_categories (category_name, category_type, parent_category_id, is_active, created_at, updated_at)
               VALUES (?, ?, NULL, ?, ?, ?)''',
            (record['category_name'], record['category_type'], record.get('is_active', True), now, now)
        )

    # Second pass: Insert categories with parents
    child_categories = [r for r in records if 'parent_category_name' in r]
    for record in child_categories:
        # Look up parent category ID
        cursor.execute(
            'SELECT category_id FROM budget_categories WHERE category_name = ?',
            (record['parent_category_name'],)
        )
        parent_result = cursor.fetchone()
        parent_id = parent_result[0] if parent_result else None

        cursor.execute(
            '''INSERT INTO budget_categories (category_name, category_type, parent_category_id, is_active, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?)''',
            (record['category_name'], record['category_type'], parent_id, record.get('is_active', True), now, now)
        )

    logger.info("Loaded default data for budget_categories from budget_categories.json")
    return True


# Dummy auth setup to bypass JWT
auth = type("Auth", (), {})()
auth.current_user = {"username": "admin"}
auth.check_permission = lambda p: True
app = Flask(__name__)

# Initialize security headers for all responses
try:
    from university_system.infrastructure.security.flask_security_headers import init_security_headers
    init_security_headers(app)
except ImportError:
    pass  # Security headers module not available

# Encryption key for sensitive data
ENCRYPTION_KEY = Fernet.generate_key()
cipher_suite = Fernet(ENCRYPTION_KEY)

# Payment gateway configurations
PAYMENT_GATEWAYS = {
    'stripe': {
        'public_key': 'pk_test_...',
        'secret_key': 'sk_test_...',
        'webhook_secret': 'whsec_...'
    },
    'paypal': {
        'client_id': 'your_paypal_client_id',
        'client_secret': 'your_paypal_client_secret',
        'environment': 'sandbox'  # or 'live'
    }
}

# Currency exchange API configuration
# WARNING: Never commit real API keys to version control!
# Set these environment variables in your deployment environment
SUPPORTED_CURRENCIES = ['GBP', 'USD', 'EUR', 'CAD', 'AUD']
PAYMENT_GATEWAYS = {
    'stripe': {'public_key': '', 'secret_key': '', 'webhook_secret': ''},
    'paypal': {'client_id': '', 'client_secret': '', 'environment': 'sandbox'}
}
# Load exchange API key from environment variable
EXCHANGE_API_KEY = os.getenv('EXCHANGE_API_KEY', '')

from university_system.modules.domain.finance.core.account_management import assign_fees_to_student, record_payment, generate_invoice, view_student_financial_statement, process_refund, api_record_payment, manage_student_credits
from university_system.modules.domain.finance.billing.payment_plans import create_payment_plan, manage_payment_plans, view_active_payment_plans, process_payment_plan_payment, send_payment_plan_notification, modify_payment_plan, cancel_payment_plan
from university_system.modules.domain.finance.billing.fee_structure import calculate_late_fees, waive_late_fee, update_exchange_rates, convert_currency, api_get_exchange_rates, currency_conversion_tool
from university_system.modules.domain.finance.reporting.revenue_analytics import generate_financial_reports, revenue_summary_report, generate_budget_variance_report, generate_outstanding_fees_report, generate_payment_collection_report, generate_predictive_analytics, generate_financial_dashboard, student_account_summary_report, fee_type_analysis_report, payment_method_analysis_report, monthly_revenue_trend_report, scholarship_reports, student_scholarship_report, generate_audit_report, generate_revenue_forecast, generate_forecast_values, generate_enrollment_based_forecast, create_revenue_forecast_chart, save_forecast_to_database, manage_collections, create_collection_case, send_collection_notice, generate_aid_reports, loan_repayment_status_report, generate_financial_forecasting, generate_budget_variance_forecast, generate_comprehensive_forecast_report, generate_budget_reports, budget_summary_report, variance_analysis_report, category_performance_report, assign_to_collection_agency, track_collection_progress, update_collection_case_status, generate_collection_reports, collection_performance_summary, agency_performance_report, manage_collection_agencies, view_collection_agencies, add_collection_agency, setup_collection_workflows, aging_analysis_report, collection_case_status_report, view_student_collection_detail, edit_collection_agency, deactivate_collection_agency, export_forecast_report
from university_system.modules.domain.finance.scholarships.scholarship_programs import manage_scholarships, view_available_scholarships, create_new_scholarship, award_scholarship_to_student, view_student_scholarships, scholarship_distribution_summary, scholarship_utilization_analysis, manage_financial_aid, view_financial_aid_applications, create_financial_aid_application, disburse_financial_aid
# NOTE: Some imports commented out due to missing modules - functionality needs to be implemented
# from university_system.modules.domain.finance.core.security_automation  import setup_automated_notifications, send_automated_notifications, send_notification, send_email_notification, send_sms_notification, enhanced_notification_system, detect_payment_fraud, log_audit_action, create_approval_workflow, send_aid_decision_notification, send_disbursement_notification, budget_approval_workflow, verify_jwt_in_request, api_endpoint
# from university_system.modules.domain.finance.finance_budgeting_collection import manage_budgets, create_budget_plan, add_budget_line_items, view_budget_plans, view_budget_plan_detail, update_budget_plan, update_budget_line_items, recalculate_budget_totals, budget_vs_actual_analysis, manage_budget_categories, view_budget_categories, create_budget_category, edit_budget_category, deactivate_budget_category, budget_performance_trends
try:
    # finance_misc is optional in some deployments; keep the import best-effort
    from university_system.modules.domain.finance.core import set_auth as set_finance_misc_auth
except ImportError:
    set_finance_misc_auth = None


def set_finance_auth(auth_instance):
    global auth
    # Store the provided authentication object instead of unconditionally
    # resetting it to ``None``.  Without this, downstream functions that
    # reference ``auth.current_user`` or ``auth.check_permission`` will crash.
    auth = auth_instance
    if set_finance_misc_auth:
        set_finance_misc_auth(auth_instance)
    else:
        logger.debug("finance_misc module not available; skipping misc auth configuration")

def init_enhanced_finance_db():
    """Initialize the enhanced finance database with all new tables"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        # Create scholarships table if it doesn't exist
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS scholarships (
            scholarship_id INTEGER PRIMARY KEY AUTOINCREMENT,
            scholarship_name TEXT NOT NULL,
            description TEXT,
            amount DECIMAL(10,2),
            academic_year TEXT,
            criteria TEXT,
            deadline TEXT,
            is_active BOOLEAN DEFAULT 1,
            created_at TEXT,
            updated_at TEXT
        )
        ''')
        
        # Create student_scholarships table if it doesn't exist
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS student_scholarships (
            student_scholarship_id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id TEXT NOT NULL,
            scholarship_id INTEGER NOT NULL,
            amount DECIMAL(10,2) NOT NULL,
            status TEXT DEFAULT 'active',
            awarded_date TEXT,
            created_at TEXT,
            FOREIGN KEY (student_id) REFERENCES students (student_id),
            FOREIGN KEY (scholarship_id) REFERENCES scholarships (scholarship_id)
        )
        ''')
        
        # Fee types table
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS fee_types (
            fee_type_id INTEGER PRIMARY KEY AUTOINCREMENT,
            fee_name TEXT NOT NULL,
            description TEXT,
            is_recurring BOOLEAN DEFAULT 0,
            academic_year TEXT,
            is_late_fee BOOLEAN DEFAULT 0,
            late_fee_calculation TEXT, -- 'fixed', 'percentage', 'daily'
            late_fee_amount DECIMAL(10,2),
            grace_period_days INTEGER DEFAULT 0,
            created_at TEXT,
            updated_at TEXT
        )
        ''')
        
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS program_fees (
            program_fee_id INTEGER PRIMARY KEY AUTOINCREMENT,
            fee_type_id INTEGER,
            course TEXT NOT NULL,
            amount DECIMAL(10,2) NOT NULL,
            currency TEXT DEFAULT 'GBP',
            academic_year TEXT,
            due_date TEXT,
            early_payment_discount DECIMAL(5,2) DEFAULT 0,
            early_payment_days INTEGER DEFAULT 0,
            created_at TEXT,
            updated_at TEXT,
            FOREIGN KEY (fee_type_id) REFERENCES fee_types (fee_type_id)
        )
        ''')
        
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS student_fees (
            student_fee_id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id TEXT NOT NULL,
            fee_type_id INTEGER NOT NULL,
            amount DECIMAL(10,2) NOT NULL,
            currency TEXT DEFAULT 'GBP',
            status TEXT DEFAULT 'unpaid',
            due_date TEXT,
            last_reminder_sent TEXT,
            reminder_count INTEGER DEFAULT 0,
            created_at TEXT,
            updated_at TEXT,
            FOREIGN KEY (student_id) REFERENCES students (student_id),
            FOREIGN KEY (fee_type_id) REFERENCES fee_types (fee_type_id)
        )
        ''')
        
        # Enhanced payments table
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS payments (
            payment_id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id TEXT NOT NULL,
            amount DECIMAL(10,2) NOT NULL,
            currency TEXT DEFAULT 'GBP',
            payment_method TEXT,
            gateway_transaction_id TEXT,
            gateway_name TEXT,
            transaction_id TEXT,
            payment_date TEXT,
            status TEXT DEFAULT 'completed', -- pending, completed, failed, refunded
            notes TEXT,
            created_by TEXT,
            created_at TEXT,
            fraud_score DECIMAL(3,2),
            is_suspicious BOOLEAN DEFAULT 0,
            FOREIGN KEY (student_id) REFERENCES students (student_id)
        )
        ''')
        
        # Payment allocations
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS payment_allocations (
            allocation_id INTEGER PRIMARY KEY AUTOINCREMENT,
            payment_id INTEGER NOT NULL,
            student_fee_id INTEGER NOT NULL,
            amount DECIMAL(10,2) NOT NULL,
            created_at TEXT,
            FOREIGN KEY (payment_id) REFERENCES payments (payment_id),
            FOREIGN KEY (student_fee_id) REFERENCES student_fees (student_fee_id)
        )
        ''')
        
        # Payment Plans System
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS payment_plan_templates (
            template_id INTEGER PRIMARY KEY AUTOINCREMENT,
            template_name TEXT NOT NULL,
            description TEXT,
            number_of_installments INTEGER NOT NULL,
            installment_frequency TEXT NOT NULL, -- 'weekly', 'monthly', 'quarterly'
            setup_fee DECIMAL(10,2) DEFAULT 0,
            interest_rate DECIMAL(5,2) DEFAULT 0,
            early_payment_discount DECIMAL(5,2) DEFAULT 0,
            late_payment_penalty DECIMAL(5,2) DEFAULT 0,
            is_active BOOLEAN DEFAULT 1,
            created_at TEXT,
            updated_at TEXT
        )
        ''')
        
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS student_payment_plans (
            payment_plan_id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id TEXT NOT NULL,
            template_id INTEGER,
            total_amount DECIMAL(10,2) NOT NULL,
            remaining_amount DECIMAL(10,2) NOT NULL,
            currency TEXT DEFAULT 'GBP',
            status TEXT DEFAULT 'active', -- active, completed, defaulted, cancelled
            start_date TEXT NOT NULL,
            next_due_date TEXT,
            setup_fee_paid BOOLEAN DEFAULT 0,
            auto_payment_enabled BOOLEAN DEFAULT 0,
            payment_method_id INTEGER,
            notes TEXT,
            created_at TEXT,
            updated_at TEXT,
            FOREIGN KEY (student_id) REFERENCES students (student_id),
            FOREIGN KEY (template_id) REFERENCES payment_plan_templates (template_id)
        )
        ''')
        
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS payment_plan_installments (
            installment_id INTEGER PRIMARY KEY AUTOINCREMENT,
            payment_plan_id INTEGER NOT NULL,
            installment_number INTEGER NOT NULL,
            amount DECIMAL(10,2) NOT NULL,
            due_date TEXT NOT NULL,
            status TEXT DEFAULT 'pending', -- pending, paid, overdue, waived
            payment_id INTEGER,
            late_fee_amount DECIMAL(10,2) DEFAULT 0,
            created_at TEXT,
            updated_at TEXT,
            FOREIGN KEY (payment_plan_id) REFERENCES student_payment_plans (payment_plan_id),
            FOREIGN KEY (payment_id) REFERENCES payments (payment_id)
        )
        ''')
        
        # Refunds and Credits System
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS refunds (
            refund_id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id TEXT NOT NULL,
            original_payment_id INTEGER,
            refund_amount DECIMAL(10,2) NOT NULL,
            currency TEXT DEFAULT 'GBP',
            refund_reason TEXT NOT NULL,
            refund_type TEXT NOT NULL, -- 'full', 'partial', 'withdrawal'
            refund_method TEXT, -- 'bank_transfer', 'original_payment_method', 'check'
            status TEXT DEFAULT 'pending', -- pending, approved, processed, rejected
            requested_by TEXT,
            approved_by TEXT,
            processed_by TEXT,
            request_date TEXT,
            approval_date TEXT,
            processed_date TEXT,
            notes TEXT,
            created_at TEXT,
            FOREIGN KEY (student_id) REFERENCES students (student_id),
            FOREIGN KEY (original_payment_id) REFERENCES payments (payment_id)
        )
        ''')
        
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS student_credits (
            credit_id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id TEXT NOT NULL,
            credit_amount DECIMAL(10,2) NOT NULL,
            currency TEXT DEFAULT 'GBP',
            credit_source TEXT, -- 'overpayment', 'refund', 'scholarship', 'adjustment'
            description TEXT,
            expiry_date TEXT,
            remaining_amount DECIMAL(10,2) NOT NULL,
            status TEXT DEFAULT 'active', -- active, used, expired
            created_by TEXT,
            created_at TEXT,
            updated_at TEXT,
            FOREIGN KEY (student_id) REFERENCES students (student_id)
        )
        ''')
        
        # Late Fees and Penalties
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS late_fees (
            late_fee_id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_fee_id INTEGER NOT NULL,
            late_fee_amount DECIMAL(10,2) NOT NULL,
            calculation_method TEXT, -- 'fixed', 'percentage', 'daily'
            days_overdue INTEGER NOT NULL,
            applied_date TEXT NOT NULL,
            waived BOOLEAN DEFAULT 0,
            waived_by TEXT,
            waived_date TEXT,
            waiver_reason TEXT,
            created_at TEXT,
            FOREIGN KEY (student_fee_id) REFERENCES student_fees (student_fee_id)
        )
        ''')
        
        # Multi-Currency Support
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS exchange_rates (
            rate_id INTEGER PRIMARY KEY AUTOINCREMENT,
            from_currency TEXT NOT NULL,
            to_currency TEXT NOT NULL,
            exchange_rate DECIMAL(10,6) NOT NULL,
            rate_date TEXT NOT NULL,
            source TEXT, -- 'manual', 'api', 'bank'
            created_at TEXT
        )
        ''')
        
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS currency_settings (
            setting_id INTEGER PRIMARY KEY AUTOINCREMENT,
            base_currency TEXT DEFAULT 'GBP',
            auto_update_rates BOOLEAN DEFAULT 1,
            rate_update_frequency INTEGER DEFAULT 24, -- hours
            last_rate_update TEXT,
            created_at TEXT,
            updated_at TEXT
        )
        ''')
        
        # Financial Aid and Loans
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS financial_aid_types (
            aid_type_id INTEGER PRIMARY KEY AUTOINCREMENT,
            aid_name TEXT NOT NULL,
            aid_category TEXT, -- 'grant', 'loan', 'work_study', 'emergency'
            description TEXT,
            max_amount DECIMAL(10,2),
            eligibility_criteria TEXT,
            application_deadline TEXT,
            is_renewable BOOLEAN DEFAULT 0,
            requires_repayment BOOLEAN DEFAULT 0,
            interest_rate DECIMAL(5,2),
            grace_period_months INTEGER,
            is_active BOOLEAN DEFAULT 1,
            created_at TEXT,
            updated_at TEXT
        )
        ''')
        
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS student_financial_aid (
            aid_id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id TEXT NOT NULL,
            aid_type_id INTEGER NOT NULL,
            awarded_amount DECIMAL(10,2) NOT NULL,
            disbursed_amount DECIMAL(10,2) DEFAULT 0,
            remaining_amount DECIMAL(10,2) NOT NULL,
            currency TEXT DEFAULT 'GBP',
            status TEXT DEFAULT 'pending', -- pending, approved, disbursed, completed, cancelled
            application_date TEXT,
            approval_date TEXT,
            disbursement_schedule TEXT, -- JSON with disbursement dates and amounts
            repayment_start_date TEXT,
            monthly_payment_amount DECIMAL(10,2),
            total_repaid DECIMAL(10,2) DEFAULT 0,
            approved_by TEXT,
            notes TEXT,
            created_at TEXT,
            updated_at TEXT,
            FOREIGN KEY (student_id) REFERENCES students (student_id),
            FOREIGN KEY (aid_type_id) REFERENCES financial_aid_types (aid_type_id)
        )
        ''')
        
        # Budgeting and Forecasting
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS budget_categories (
            category_id INTEGER PRIMARY KEY AUTOINCREMENT,
            category_name TEXT NOT NULL,
            category_type TEXT NOT NULL, -- 'revenue', 'expense'
            parent_category_id INTEGER,
            is_active BOOLEAN DEFAULT 1,
            created_at TEXT,
            updated_at TEXT,
            FOREIGN KEY (parent_category_id) REFERENCES budget_categories (category_id)
        )
        ''')
        
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS budget_plans (
            budget_id INTEGER PRIMARY KEY AUTOINCREMENT,
            plan_name TEXT NOT NULL,
            academic_year TEXT NOT NULL,
            currency TEXT DEFAULT 'GBP',
            status TEXT DEFAULT 'draft', -- draft, approved, active, closed
            total_revenue_budget DECIMAL(12,2) DEFAULT 0,
            total_expense_budget DECIMAL(12,2) DEFAULT 0,
            created_by TEXT,
            approved_by TEXT,
            notes TEXT,
            created_at TEXT,
            updated_at TEXT
        )
        ''')
        
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS budget_line_items (
            line_item_id INTEGER PRIMARY KEY AUTOINCREMENT,
            budget_id INTEGER NOT NULL,
            category_id INTEGER NOT NULL,
            budgeted_amount DECIMAL(12,2) NOT NULL,
            actual_amount DECIMAL(12,2) DEFAULT 0,
            variance DECIMAL(12,2) DEFAULT 0,
            notes TEXT,
            created_at TEXT,
            updated_at TEXT,
            FOREIGN KEY (budget_id) REFERENCES budget_plans (budget_id),
            FOREIGN KEY (category_id) REFERENCES budget_categories (category_id)
        )
        ''')
        
        # Automated Notifications
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS notification_templates (
            template_id INTEGER PRIMARY KEY AUTOINCREMENT,
            template_name TEXT NOT NULL,
            template_type TEXT NOT NULL, -- 'payment_reminder', 'overdue_notice', 'payment_confirmation', etc.
            subject_template TEXT NOT NULL,
            body_template TEXT NOT NULL,
            send_method TEXT DEFAULT 'email', -- 'email', 'sms', 'push'
            is_active BOOLEAN DEFAULT 1,
            created_at TEXT,
            updated_at TEXT
        )
        ''')
        
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS notification_schedules (
            schedule_id INTEGER PRIMARY KEY AUTOINCREMENT,
            template_id INTEGER NOT NULL,
            trigger_condition TEXT NOT NULL, -- JSON with conditions
            days_before_due INTEGER,
            max_reminders INTEGER DEFAULT 3,
            reminder_interval_days INTEGER DEFAULT 7,
            is_active BOOLEAN DEFAULT 1,
            created_at TEXT,
            updated_at TEXT,
            FOREIGN KEY (template_id) REFERENCES notification_templates (template_id)
        )
        ''')
        
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS sent_notifications (
            notification_id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id TEXT NOT NULL,
            template_id INTEGER NOT NULL,
            recipient_email TEXT,
            recipient_phone TEXT,
            subject TEXT,
            message_body TEXT,
            send_method TEXT,
            status TEXT DEFAULT 'pending', -- pending, sent, failed, bounced
            sent_at TEXT,
            error_message TEXT,
            created_at TEXT,
            FOREIGN KEY (student_id) REFERENCES students (student_id),
            FOREIGN KEY (template_id) REFERENCES notification_templates (template_id)
        )
        ''')
        
        # Analytics and Reporting
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS financial_kpis (
            kpi_id INTEGER PRIMARY KEY AUTOINCREMENT,
            kpi_name TEXT NOT NULL,
            kpi_value DECIMAL(15,2) NOT NULL,
            kpi_type TEXT NOT NULL, -- 'amount', 'percentage', 'count', 'ratio'
            calculation_period TEXT NOT NULL, -- 'daily', 'weekly', 'monthly', 'yearly'
            calculation_date TEXT NOT NULL,
            academic_year TEXT,
            created_at TEXT
        )
        ''')
        
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS payment_risk_scores (
            score_id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id TEXT NOT NULL,
            risk_score DECIMAL(5,2) NOT NULL, -- 0-100
            risk_level TEXT NOT NULL, -- 'low', 'medium', 'high'
            factors TEXT, -- JSON with risk factors
            last_calculated TEXT,
            created_at TEXT,
            FOREIGN KEY (student_id) REFERENCES students (student_id)
        )
        ''')
        
        # External Integrations
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS payment_gateways (
            gateway_id INTEGER PRIMARY KEY AUTOINCREMENT,
            gateway_name TEXT NOT NULL,
            gateway_type TEXT NOT NULL, -- 'stripe', 'paypal', 'bank_transfer', etc.
            configuration TEXT, -- JSON with gateway config
            is_active BOOLEAN DEFAULT 1,
            transaction_fee_percentage DECIMAL(5,4),
            transaction_fee_fixed DECIMAL(10,2),
            supported_currencies TEXT, -- JSON array
            webhook_url TEXT,
            created_at TEXT,
            updated_at TEXT
        )
        ''')
        
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS gateway_transactions (
            transaction_id INTEGER PRIMARY KEY AUTOINCREMENT,
            payment_id INTEGER,
            gateway_id INTEGER NOT NULL,
            gateway_transaction_id TEXT NOT NULL,
            amount DECIMAL(10,2) NOT NULL,
            currency TEXT NOT NULL,
            status TEXT NOT NULL,
            gateway_fee DECIMAL(10,2),
            raw_response TEXT, -- JSON response from gateway
            webhook_verified BOOLEAN DEFAULT 0,
            created_at TEXT,
            updated_at TEXT,
            FOREIGN KEY (payment_id) REFERENCES payments (payment_id),
            FOREIGN KEY (gateway_id) REFERENCES payment_gateways (gateway_id)
        )
        ''')
        
        # Audit and Compliance
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS audit_log (
            log_id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT,
            action TEXT NOT NULL,
            table_name TEXT,
            record_id TEXT,
            old_values TEXT, -- JSON
            new_values TEXT, -- JSON
            ip_address TEXT,
            user_agent TEXT,
            session_id TEXT,
            timestamp TEXT NOT NULL
        )
        ''')
        
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS data_retention_policies (
            policy_id INTEGER PRIMARY KEY AUTOINCREMENT,
            data_type TEXT NOT NULL,
            retention_period_months INTEGER NOT NULL,
            deletion_method TEXT DEFAULT 'soft', -- 'soft', 'hard', 'anonymize'
            last_cleanup_date TEXT,
            is_active BOOLEAN DEFAULT 1,
            created_at TEXT,
            updated_at TEXT
        )
        ''')
        
        # API and Integration
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS api_keys (
            key_id INTEGER PRIMARY KEY AUTOINCREMENT,
            key_name TEXT NOT NULL,
            api_key TEXT NOT NULL,
            key_hash TEXT NOT NULL,
            permissions TEXT, -- JSON array
            rate_limit INTEGER DEFAULT 1000,
            is_active BOOLEAN DEFAULT 1,
            expires_at TEXT,
            last_used_at TEXT,
            created_by TEXT,
            created_at TEXT
        )
        ''')
        
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS api_usage_log (
            usage_id INTEGER PRIMARY KEY AUTOINCREMENT,
            api_key_id INTEGER,
            endpoint TEXT NOT NULL,
            method TEXT NOT NULL,
            ip_address TEXT,
            user_agent TEXT,
            response_status INTEGER,
            response_time_ms INTEGER,
            timestamp TEXT NOT NULL,
            FOREIGN KEY (api_key_id) REFERENCES api_keys (key_id)
        )
        ''')
        
        # Collection Management
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS collection_agencies (
            agency_id INTEGER PRIMARY KEY AUTOINCREMENT,
            agency_name TEXT NOT NULL,
            contact_email TEXT,
            contact_phone TEXT,
            commission_rate DECIMAL(5,2),
            minimum_amount DECIMAL(10,2),
            is_active BOOLEAN DEFAULT 1,
            created_at TEXT,
            updated_at TEXT
        )
        ''')
        
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS collection_cases (
            case_id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id TEXT NOT NULL,
            agency_id INTEGER,
            total_debt DECIMAL(10,2) NOT NULL,
            case_status TEXT DEFAULT 'new', -- new, assigned, in_progress, resolved, closed
            assigned_date TEXT,
            resolution_date TEXT,
            amount_collected DECIMAL(10,2) DEFAULT 0,
            commission_paid DECIMAL(10,2) DEFAULT 0,
            notes TEXT,
            created_at TEXT,
            updated_at TEXT,
            FOREIGN KEY (student_id) REFERENCES students (student_id),
            FOREIGN KEY (agency_id) REFERENCES collection_agencies (agency_id)
        )
        ''')
        
        # Workflow System
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS workflows (
            workflow_id INTEGER PRIMARY KEY AUTOINCREMENT,
            workflow_name TEXT NOT NULL,
            workflow_type TEXT NOT NULL, -- 'approval', 'notification', 'automation'
            trigger_conditions TEXT, -- JSON
            workflow_steps TEXT, -- JSON with step definitions
            is_active BOOLEAN DEFAULT 1,
            created_by TEXT,
            created_at TEXT,
            updated_at TEXT
        )
        ''')
        
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS workflow_instances (
            instance_id INTEGER PRIMARY KEY AUTOINCREMENT,
            workflow_id INTEGER NOT NULL,
            entity_type TEXT NOT NULL, -- 'refund', 'payment_plan', 'scholarship', etc.
            entity_id INTEGER NOT NULL,
            current_step INTEGER DEFAULT 1,
            status TEXT DEFAULT 'pending', -- pending, in_progress, completed, cancelled
            assigned_to TEXT,
            started_at TEXT,
            completed_at TEXT,
            metadata TEXT, -- JSON with instance-specific data
            FOREIGN KEY (workflow_id) REFERENCES workflows (workflow_id)
        )
        ''')
        
        # Initialize default data
        init_default_enhanced_data(cursor)
        
        conn.commit()
        conn.close()
        print(get_text("finance.core.db_init_success", default="Enhanced finance database initialized successfully!"))
        
    except sqlite3.Error as e:
        print(get_text("finance.core.db_init_error", default="An error occurred while initializing the enhanced finance database: {error}").format(error=e))
        if 'conn' in locals():
            conn.close()

def init_default_enhanced_data(cursor):
    """Load default data from JSON templates if tables are empty."""
    # Define table configurations: (table_name, json_file, columns_map, warning_message)
    table_configs = [
        (
            'payment_plan_templates',
            'payment_plan_templates.json',
            {
                'template_name': 'template_name',
                'description': 'description',
                'number_of_installments': 'number_of_installments',
                'installment_frequency': 'installment_frequency',
                'setup_fee': 'setup_fee',
                'interest_rate': 'interest_rate',
                'early_payment_discount': 'early_payment_discount',
                'late_payment_penalty': 'late_payment_penalty',
                'is_active': 'is_active',
                'created_at': 'created_at',
                'updated_at': 'updated_at'
            },
            'No payment plan templates found. Add templates via the finance administration tools.'
        ),
        (
            'notification_templates',
            'notification_templates.json',
            {
                'template_name': 'template_name',
                'template_type': 'template_type',
                'subject_template': 'subject_template',
                'body_template': 'body_template',
                'send_method': 'send_method',
                'is_active': 'is_active',
                'created_at': 'created_at',
                'updated_at': 'updated_at'
            },
            'Notification templates table is empty. Configure email templates before enabling automation.'
        ),
        (
            'financial_aid_types',
            'financial_aid_types.json',
            {
                'aid_name': 'aid_name',
                'aid_category': 'aid_category',
                'description': 'description',
                'max_amount': 'max_amount',
                'eligibility_criteria': 'eligibility_criteria',
                'application_deadline': 'application_deadline',
                'is_renewable': 'is_renewable',
                'requires_repayment': 'requires_repayment',
                'interest_rate': 'interest_rate',
                'grace_period_months': 'grace_period_months',
                'is_active': 'is_active',
                'created_at': 'created_at',
                'updated_at': 'updated_at'
            },
            'Financial aid types table is empty. Import the financial aid catalogue to continue.'
        ),
        (
            'exchange_rates',
            'exchange_rates.json',
            {
                'from_currency': 'from_currency',
                'to_currency': 'to_currency',
                'exchange_rate': 'exchange_rate',
                'source': 'source',
                'rate_date': 'rate_date',
                'created_at': 'created_at'
            },
            'Exchange rates table is empty. Import exchange rates or enable automatic updates.'
        ),
        (
            'currency_settings',
            'currency_settings.json',
            {
                'base_currency': 'base_currency',
                'auto_update_rates': 'auto_update_rates',
                'rate_update_frequency': 'rate_update_frequency',
                'created_at': 'created_at',
                'updated_at': 'updated_at'
            },
            'Currency settings table is empty. Define base currency and update frequency via finance settings.'
        ),
        (
            'fee_types',
            'fee_types.json',
            {
                'fee_name': 'fee_name',
                'description': 'description',
                'is_recurring': 'is_recurring',
                'academic_year': 'academic_year',
                'is_late_fee': 'is_late_fee',
                'late_fee_calculation': 'late_fee_calculation',
                'late_fee_amount': 'late_fee_amount',
                'grace_period_days': 'grace_period_days',
                'created_at': 'created_at',
                'updated_at': 'updated_at'
            },
            'Fee types table is empty. Create fee types to manage student billing.'
        ),
        (
            'scholarships',
            'scholarships.json',
            {
                'scholarship_name': 'scholarship_name',
                'description': 'description',
                'amount': 'amount',
                'academic_year': 'academic_year',
                'criteria': 'criteria',
                'deadline': 'deadline',
                'is_active': 'is_active',
                'created_at': 'created_at',
                'updated_at': 'updated_at'
            },
            'Scholarship catalogue is empty. Add scholarships through the finance admin interface.'
        ),
    ]

    # Process each table configuration
    for table_name, json_file, columns_map, warning_message in table_configs:
        seeded = seed_table_from_json(cursor, table_name, json_file, columns_map)
        if seeded:
            logger.info(f"Loaded default data for {table_name} from {json_file}")
        else:
            # If seeding failed or table was already populated, check if still empty
            warn_if_table_empty(cursor, table_name, warning_message)

    # Handle budget_categories separately due to parent-child relationships
    seed_budget_categories(cursor)

def initialize_finance():
    """Initialize the finance database"""
    global auth
    
    print(get_text("finance.core.initializing", default="Initializing Enhanced Finance Management System..."))

    # Import and use centralized authentication system
    from university_system.infrastructure.auth import UserAuth
    auth = get_auth()
    if auth is None:
        auth = UserAuth()

    # Initialize database
    init_enhanced_finance_db()
    
    conn = get_connection()
    try:
        cursor = conn.cursor()
        warn_if_table_empty(
            cursor,
            'students',
            'No student records found. Finance workflows require student data to be present in the database.'
        )
    finally:
        conn.close()
    
    print(get_text("finance.core.init_success", default="Finance system initialized successfully!"))

def display_enhanced_finance_menu():
    """Display the enhanced finance management menu"""
    global auth

    # Always get auth from shared context to ensure we have the logged-in user
    shared_auth = get_auth()
    if shared_auth and shared_auth.current_user:
        auth = shared_auth
    elif not auth or not hasattr(auth, 'current_user') or not auth.current_user:
        print(get_text('finance.not_logged_in', default='You must be logged in to access enhanced finance features.'))
        return

    # Initialize system
    initialize_finance()

    while True:
        print("\n" + "=" * 100)
        print(get_text("finance.core.title", default="ENHANCED FINANCE MANAGEMENT SYSTEM"))
        print("=" * 100)

        # Core Finance Operations
        print(f"\n{get_text('finance.core.section.core', default='CORE FINANCE OPERATIONS')}:")
        if auth.check_permission('manage_finances'):
            print(f"{'1.  ' + get_text('finance.core.menu.assign_fees', default='Assign Fees'):<25} {'2.  ' + get_text('finance.core.menu.record_payment', default='Record Payment'):<25} {'3.  ' + get_text('finance.core.menu.generate_invoice', default='Generate Invoice'):<25} {'4.  ' + get_text('finance.core.menu.process_refund', default='Process Refund'):<25}")
            print(f"{'5.  ' + get_text('finance.core.menu.student_credits', default='Student Credits'):<25} {'6.  ' + get_text('finance.core.menu.financial_statement', default='Financial Statement'):<25}")
        else:
            print(f"{'6.  ' + get_text('finance.core.menu.financial_statement', default='Financial Statement'):<25}")

        # Payment Plans
        print(f"\n{get_text('finance.core.section.payment_plans', default='PAYMENT PLANS')}:")
        if auth.check_permission('manage_finances'):
            print(f"{'7.  ' + get_text('finance.core.menu.manage_plans', default='Manage Plans'):<25} {'8.  ' + get_text('finance.core.menu.process_plan_payment', default='Process Payment'):<25}")

        # Late Fees and Penalties
        print(f"\n{get_text('finance.core.section.late_fees', default='LATE FEES & PENALTIES')}:")
        if auth.check_permission('manage_finances'):
            print(f"{'9.  ' + get_text('finance.core.menu.calculate_late_fees', default='Calculate Late Fees'):<25} {'10. ' + get_text('finance.core.menu.waive_late_fee', default='Waive Late Fee'):<25}")

        # Multi-Currency
        print(f"\n{get_text('finance.core.section.currency', default='MULTI-CURRENCY')}:")
        if auth.check_permission('manage_finances'):
            print(f"{'11. ' + get_text('finance.core.menu.exchange_rates', default='Exchange Rates'):<25} {'12. ' + get_text('finance.core.menu.currency_converter', default='Currency Converter'):<25}")

        # Analytics and Reporting
        print(f"\n{get_text('finance.core.section.analytics', default='ANALYTICS & REPORTING')}:")
        if auth.check_permission('manage_finances'):
            print(f"{'13. ' + get_text('finance.core.menu.finance_dashboard', default='Finance Dashboard'):<25} {'14. ' + get_text('finance.core.menu.predictive_analytics', default='Predictive Analytics'):<25} {'15. ' + get_text('finance.core.menu.financial_reports', default='Financial Reports'):<25} {'16. ' + get_text('finance.core.menu.outstanding_fees', default='Outstanding Fees'):<25}")
            print(f"{'17. ' + get_text('finance.core.menu.collection_report', default='Collection Report'):<25}")

        # Scholarships and Financial Aid
        print(f"\n{get_text('finance.core.section.scholarships', default='SCHOLARSHIPS & FINANCIAL AID')}:")
        if auth.check_permission('manage_finances'):
            print(f"{'18. ' + get_text('finance.core.menu.manage_scholarships', default='Manage Scholarships'):<25} {'19. ' + get_text('finance.core.menu.financial_aid', default='Financial Aid'):<25}")

        # Security and Compliance
        print(f"\n{get_text('finance.core.section.security', default='SECURITY & COMPLIANCE')}:")
        if auth.check_permission('manage_finances'):
            print(f"{'20. ' + get_text('finance.core.menu.fraud_detection', default='Fraud Detection'):<25} {'21. ' + get_text('finance.core.menu.audit_report', default='Audit Report'):<25} {'22. ' + get_text('finance.core.menu.manage_workflows', default='Manage Workflows'):<25}")

        # Automation
        print(f"\n🤖 {get_text('finance.section.automation', default='AUTOMATION')}:")
        if auth.check_permission('manage_finances'):
            print(f"{'23. ' + get_text('finance.menu.setup_notifications', default='Setup Notifications'):<25} {'24. ' + get_text('finance.menu.send_notifications', default='Send Notifications'):<25}")

        # Budgeting
        print(f"\n💼 {get_text('finance.section.budgeting', default='BUDGETING & FORECASTING')}:")
        if auth.check_permission('manage_finances'):
            print(f"{'25. ' + get_text('finance.menu.budget_management', default='Budget Management'):<25} {'26. ' + get_text('finance.menu.revenue_forecasting', default='Revenue Forecasting'):<25}")

        # Collection Management
        print(f"\n📞 {get_text('finance.section.collection', default='COLLECTION MANAGEMENT')}:")
        if auth.check_permission('manage_finances'):
            print(f"{'27. ' + get_text('finance.menu.collection_mgmt', default='Collection Mgmt'):<25}")

        # Advanced Reports Menu
        print(f"\n📊 {get_text('finance.section.advanced_reports', default='ADVANCED REPORTS')}:")
        if auth.check_permission('manage_finances'):
            print(f"{'28. ' + get_text('finance.menu.advanced_reports_menu', default='Advanced Reports Menu'):<25}")

        print(f"\n⚙️  {get_text('finance.section.system', default='SYSTEM')}:")
        print(f"{'29. ' + get_text('finance.menu.language', default='Language'):<25} {'30. ' + get_text('finance.menu.initialize', default='Initialize (Reset)'):<25} {'31. ' + get_text('finance.menu.exit', default='Exit'):<25}")
        print("=" * 100)

        choice = input(get_text('finance.prompt.choice', default='Enter your choice') + ": ").strip()

        try:
            # Core Finance Operations
            if choice == '1' and auth.check_permission('manage_finances'):
                assign_fees_to_student()
            elif choice == '2' and auth.check_permission('manage_finances'):
                record_payment()
            elif choice == '3' and auth.check_permission('manage_finances'):
                generate_invoice()
            elif choice == '4' and auth.check_permission('manage_finances'):
                process_refund()
            elif choice == '5' and auth.check_permission('manage_finances'):
                manage_student_credits()
            elif choice == '6':
                view_student_financial_statement()

            # Payment Plans
            elif choice == '7' and auth.check_permission('manage_finances'):
                manage_payment_plans()
            elif choice == '8' and auth.check_permission('manage_finances'):
                process_payment_plan_payment()

            # Late Fees
            elif choice == '9' and auth.check_permission('manage_finances'):
                calculate_late_fees()
            elif choice == '10' and auth.check_permission('manage_finances'):
                waive_late_fee()

            # Multi-Currency
            elif choice == '11' and auth.check_permission('manage_finances'):
                update_exchange_rates()
            elif choice == '12' and auth.check_permission('manage_finances'):
                currency_conversion_tool()

            # Analytics
            elif choice == '13' and auth.check_permission('manage_finances'):
                generate_financial_dashboard()
            elif choice == '14' and auth.check_permission('manage_finances'):
                generate_predictive_analytics()
            elif choice == '15' and auth.check_permission('manage_finances'):
                generate_financial_reports()
            elif choice == '16' and auth.check_permission('manage_finances'):
                generate_outstanding_fees_report()
            elif choice == '17' and auth.check_permission('manage_finances'):
                generate_payment_collection_report()

            # Scholarships
            elif choice == '18' and auth.check_permission('manage_finances'):
                manage_scholarships()
            elif choice == '19' and auth.check_permission('manage_finances'):
                manage_financial_aid()

            # Security
            elif choice == '20' and auth.check_permission('manage_finances'):
                detect_payment_fraud()
            elif choice == '21' and auth.check_permission('view_audit_logs'):
                start_date = input("Enter start date (YYYY-MM-DD): ").strip()
                end_date = input("Enter end date (YYYY-MM-DD): ").strip()
                generate_audit_report(start_date, end_date)
            elif choice == '22' and auth.check_permission('manage_workflows'):
                create_approval_workflow()

            # Automation
            elif choice == '23' and auth.check_permission('manage_finances'):
                setup_automated_notifications()
            elif choice == '24' and auth.check_permission('manage_finances'):
                notifications_sent = send_automated_notifications()
                print(f"Sent {notifications_sent} notifications")

            # Budgeting
            elif choice == '25' and auth.check_permission('manage_finances'):
                manage_budgets()
            elif choice == '26' and auth.check_permission('manage_finances'):
                generate_revenue_forecast()

            # Collection
            elif choice == '27' and auth.check_permission('manage_finances'):
                manage_collections()

            # Advanced Reports Menu
            elif choice == '28' and auth.check_permission('manage_finances'):
                from university_system.modules.domain.finance.reporting.financial_reports import display_enhanced_finance_menu as display_finance_reporting_menu
                display_finance_reporting_menu()

            elif choice == '29':
                display_language_menu_option()
            elif choice == '30':
                initialize_finance()
            elif choice == '31':
                print(get_text('finance.returning', default='Returning to main menu...'))
                return
            else:
                print(get_text('finance.invalid_choice', default='Invalid choice or insufficient permissions. Please try again.'))

        except Exception as e:
            print(get_text('finance.error', default='An error occurred: {error}').format(error=e))
            logging.error(f"Finance menu error: {e}")
