from university_system.infrastructure.database.db import sqlite3
import os
import csv
import pandas as pd
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
from university_system.infrastructure.auth.user_authentication import UserAuth
from university_system.infrastructure.shared_context import get_auth
from university_system.infrastructure.database.db import get_connection
from university_system.utils.logging.log_config import configure_logging

# Configure logging
logger = configure_logging(name=__name__)
warnings.filterwarnings('ignore')


def warn_if_table_empty(cursor, table_name: str, warning_message: str) -> None:
    """Log a warning when expected reference data is missing."""
    cursor.execute(f'SELECT COUNT(*) FROM {table_name}')
    result = cursor.fetchone()
    if result and result[0] == 0:
        logger.warning(warning_message)


# Dummy auth setup to bypass JWT
auth = type("Auth", (), {})()
auth.current_user = {"username": "admin"}
auth.check_permission = lambda p: True
app = Flask(__name__)

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
    from university_system.modules.domain.finance.finance_misc import set_auth as set_finance_misc_auth
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
        print("Enhanced finance database initialized successfully!")
        
    except sqlite3.Error as e:
        print(f"An error occurred while initializing the enhanced finance database: {e}")
        if 'conn' in locals():
            conn.close()

def init_default_enhanced_data(cursor):
    """Ensure expected reference data exists and warn when it does not."""
    warnings_to_issue = [
        (
            'payment_plan_templates',
            'No payment plan templates found. Add templates via the finance administration tools.'
        ),
        (
            'notification_templates',
            'Notification templates table is empty. Configure email templates before enabling automation.'
        ),
        (
            'financial_aid_types',
            'Financial aid types table is empty. Import the financial aid catalogue to continue.'
        ),
        (
            'budget_categories',
            'Budget categories table is empty. Define your budgeting structure in the finance module.'
        ),
        (
            'exchange_rates',
            'Exchange rates table is empty. Import exchange rates or enable automatic updates.'
        ),
        (
            'currency_settings',
            'Currency settings table is empty. Define base currency and update frequency via finance settings.'
        ),
        (
            'fee_types',
            'Fee types table is empty. Create fee types to manage student billing.'
        ),
        (
            'scholarships',
            'Scholarship catalogue is empty. Add scholarships through the finance admin interface.'
        ),
    ]

    for table_name, message in warnings_to_issue:
        warn_if_table_empty(cursor, table_name, message)

def initialize_finance():
    """Initialize the finance database"""
    global auth
    
    print("🏦 Initializing Enhanced Finance Management System...")

    # Import and use centralized authentication system
    from university_system.infrastructure.auth.user_authentication import UserAuth
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
    
    print("✅ Finance system initialized successfully!")

def display_enhanced_finance_menu():
    """Display the enhanced finance management menu"""
    global auth
    
    # Initialize system if not already done
    if not auth:
        initialize_finance()
    
    while True:
        print("\n" + "=" * 60)
        print("ENHANCED FINANCE MANAGEMENT SYSTEM")
        print("=" * 60)
        
        # Core Finance Operations
        print("\n📊 CORE FINANCE OPERATIONS:")
        if auth.check_permission('manage_finances'):
            print("1.  Assign Fees to Student")
            print("2.  Record Payment")
            print("3.  Generate Invoice")
            print("4.  Process Refund")
            print("5.  Manage Student Credits")
        
        print("6.  View Student Financial Statement")
        
        # Payment Plans
        print("\n💳 PAYMENT PLANS:")
        if auth.check_permission('manage_finances'):
            print("7.  Manage Payment Plans")
            print("8.  Process Payment Plan Payment")
        
        # Late Fees and Penalties
        print("\n⚠️  LATE FEES & PENALTIES:")
        if auth.check_permission('manage_finances'):
            print("9.  Calculate Late Fees")
            print("10. Waive Late Fee")
        
        # Multi-Currency
        print("\n🌍 MULTI-CURRENCY:")
        if auth.check_permission('manage_finances'):
            print("11. Update Exchange Rates")
            print("12. Currency Conversion Tool")
        
        # Analytics and Reporting
        print("\n📈 ANALYTICS & REPORTING:")
        if auth.check_permission('manage_finances'):
            print("13. Generate Financial Dashboard")
            print("14. Predictive Analytics")
            print("15. Generate Financial Reports")
            print("16. Outstanding Fees Report")
            print("17. Payment Collection Report")
        
        # Scholarships and Financial Aid
        print("\n🎓 SCHOLARSHIPS & FINANCIAL AID:")
        if auth.check_permission('manage_finances'):
            print("18. Manage Scholarships")
            print("19. Manage Financial Aid")
        
        # Security and Compliance
        print("\n🔒 SECURITY & COMPLIANCE:")
        if auth.check_permission('manage_finances'):
            print("20. Run Fraud Detection")
            print("21. Generate Audit Report")
            print("22. Manage Workflows")
        
        # Automation
        print("\n🤖 AUTOMATION:")
        if auth.check_permission('manage_finances'):
            print("23. Setup Automated Notifications")
            print("24. Send Automated Notifications")
        
        # Budgeting
        print("\n💼 BUDGETING & FORECASTING:")
        if auth.check_permission('manage_finances'):
            print("25. Budget Management")
            print("26. Revenue Forecasting")
        
        # Collection Management
        print("\n📞 COLLECTION MANAGEMENT:")
        if auth.check_permission('manage_finances'):
            print("27. Collection Management")
        
        print("\n28. Initialize System (Reset)")
        print("29. Exit")
        print("=" * 60)
        
        choice = input("Enter your choice: ").strip()
        
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
            
            elif choice == '28':
                initialize_finance()
            elif choice == '29':
                print("Goodbye!")
                return
            else:
                print("Invalid choice or insufficient permissions. Please try again.")
                
        except Exception as e:
            print(f"An error occurred: {e}")
            logging.error(f"Finance menu error: {e}")
