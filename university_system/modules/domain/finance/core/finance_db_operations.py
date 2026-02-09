from __future__ import annotations

import os
from datetime import datetime
from university_system.infrastructure.database.db import sqlite3, get_connection
from university_system.modules.shared.utils.i18n import get_text

# Use centralized schema initialization
from university_system.infrastructure.database.schemas.finance_schemas import init_finance_system_db

# Auth is available via get_auth() from shared_context if needed
from university_system.infrastructure.shared_context import get_auth
from university_system.modules.domain.finance.core.students import create_sample_students

# Re-export student finance account functions from finance_integration for backward compatibility
from university_system.modules.shared.utils.finance_integration import (
    get_student_finance_account_balance,
    process_student_finance_account_payment,
    record_payment_to_finance,
)

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

        # Financial Alerts System
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS financial_alerts (
            alert_id INTEGER PRIMARY KEY AUTOINCREMENT,
            alert_type TEXT NOT NULL, -- 'payment_overdue', 'low_balance', 'high_risk_student', etc.
            priority TEXT DEFAULT 'medium', -- 'low', 'medium', 'high', 'critical'
            title TEXT NOT NULL,
            message TEXT NOT NULL,
            student_id TEXT,
            amount DECIMAL(10,2),
            currency TEXT DEFAULT 'GBP',
            status TEXT DEFAULT 'active', -- 'active', 'acknowledged', 'resolved', 'dismissed'
            created_at TEXT NOT NULL,
            acknowledged_at TEXT,
            resolved_at TEXT,
            acknowledged_by TEXT,
            resolved_by TEXT,
            metadata TEXT, -- JSON with additional alert data
            FOREIGN KEY (student_id) REFERENCES students (student_id)
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
        print(get_text("finance.db_operations.init_success"))

    except sqlite3.Error as e:
        print(f"An error occurred while initializing the enhanced finance database: {e}")
        if 'conn' in locals():
            conn.close()

def init_default_enhanced_data(cursor):
    """Initialize default data for the enhanced system"""

    # Default payment plan templates
    now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

    # Check if data already exists
    cursor.execute('SELECT COUNT(*) FROM payment_plan_templates')
    if cursor.fetchone()[0] == 0:
        payment_plan_templates = [
            ('3-Month Plan', 'Pay fees over 3 monthly installments', 3, 'monthly', 25.00, 0.00, 5.00, 2.00, 1, now, now),
            ('6-Month Plan', 'Pay fees over 6 monthly installments', 6, 'monthly', 50.00, 1.50, 5.00, 2.00, 1, now, now),
            ('Semester Plan', 'Pay fees in 2 semester installments', 2, 'quarterly', 15.00, 0.00, 3.00, 2.50, 1, now, now),
            ('Weekly Plan', 'Pay fees in weekly installments', 12, 'weekly', 10.00, 0.50, 2.00, 1.50, 1, now, now)
        ]

        cursor.executemany('''
            INSERT INTO payment_plan_templates 
            (template_name, description, number_of_installments, installment_frequency, 
             setup_fee, interest_rate, early_payment_discount, late_payment_penalty, 
             is_active, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', payment_plan_templates)

    # Sample financial alerts
    cursor.execute('SELECT COUNT(*) FROM financial_alerts')
    if cursor.fetchone()[0] == 0:
        financial_alerts = [
            ('payment_overdue', 'high', 'Overdue Payment Alert', 'Student STU003 has overdue payment of £150.00', 'STU003', 150.00, 'GBP', 'active', now, None, None, None, None, None),
            ('high_risk_student', 'medium', 'High Risk Student', 'Student flagged for payment risk assessment', 'STU002', None, 'GBP', 'active', now, None, None, None, None, None),
            ('low_balance', 'low', 'Low Account Balance', 'System account balance below threshold', None, 500.00, 'GBP', 'active', now, None, None, None, None, None)
        ]

        cursor.executemany('''
            INSERT INTO financial_alerts
            (alert_type, priority, title, message, student_id, amount, currency, status,
             created_at, acknowledged_at, resolved_at, acknowledged_by, resolved_by, metadata)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', financial_alerts)

    # Default notification templates
    cursor.execute('SELECT COUNT(*) FROM notification_templates')
    if cursor.fetchone()[0] == 0:
        # Note: Email template content is now stored in JSON files at university_system/templates/email/
        # These database entries reference those templates by type
        notification_templates = [
            ('Payment Reminder', 'payment_reminder', 'Payment Reminder - Fees Due Soon',
             'Loads from: payment_reminder.json', 'email', 1, now, now),
            ('Overdue Notice', 'overdue_notice', 'URGENT: Overdue Payment Notice',
             'Loads from: overdue_notice.json', 'email', 1, now, now),
            ('Payment Confirmation', 'payment_confirmation', 'Payment Received - Thank You',
             'Loads from: payment_confirmation_notice.json', 'email', 1, now, now),
            ('Payment Plan Setup', 'payment_plan_setup', 'Payment Plan Confirmation',
             'Loads from: payment_plan_setup.json', 'email', 1, now, now)
        ]

        cursor.executemany('''
            INSERT INTO notification_templates 
            (template_name, template_type, subject_template, body_template, send_method, is_active, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', notification_templates)

    # Default financial aid types
    cursor.execute('SELECT COUNT(*) FROM financial_aid_types')
    if cursor.fetchone()[0] == 0:
        financial_aid_types = [
            ('Emergency Grant', 'grant', 'Short-term financial assistance for emergencies', 1000.00, 'Demonstrated emergency need', None, 0, 0, None, None, 1, now, now),
            ('Student Loan', 'loan', 'Low-interest student loan', 10000.00, 'Good academic standing and financial need', None, 1, 1, 3.50, 6, 1, now, now),
            ('Work Study Program', 'work_study', 'Part-time employment program', 2000.00, 'Financial need and good academic standing', None, 1, 0, None, None, 1, now, now),
            ('Hardship Fund', 'emergency', 'Emergency financial support', 500.00, 'Unexpected financial hardship', None, 0, 0, None, None, 1, now, now)
        ]

        cursor.executemany('''
            INSERT INTO financial_aid_types 
            (aid_name, aid_category, description, max_amount, eligibility_criteria, 
             application_deadline, is_renewable, requires_repayment, interest_rate, 
             grace_period_months, is_active, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', financial_aid_types)

    # Default budget categories
    cursor.execute('SELECT COUNT(*) FROM budget_categories')
    if cursor.fetchone()[0] == 0:
        budget_categories = [
            ('Revenue', 'revenue', None, 1, now, now),
            ('Student Fees', 'revenue', 1, 1, now, now),
            ('Government Funding', 'revenue', 1, 1, now, now),
            ('Donations', 'revenue', 1, 1, now, now),
            ('Expenses', 'expense', None, 1, now, now),
            ('Staff Salaries', 'expense', 5, 1, now, now),
            ('Facilities', 'expense', 5, 1, now, now),
            ('Technology', 'expense', 5, 1, now, now),
            ('Student Services', 'expense', 5, 1, now, now)
        ]

        cursor.executemany('''
            INSERT INTO budget_categories 
            (category_name, category_type, parent_category_id, is_active, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', budget_categories)

    # Default exchange rates (sample data)
    cursor.execute('SELECT COUNT(*) FROM exchange_rates')
    if cursor.fetchone()[0] == 0:
        exchange_rates = [
            ('GBP', 'USD', 1.27, datetime.now().strftime('%Y-%m-%d'), 'api', now),
            ('GBP', 'EUR', 1.17, datetime.now().strftime('%Y-%m-%d'), 'api', now),
            ('GBP', 'CAD', 1.71, datetime.now().strftime('%Y-%m-%d'), 'api', now),
            ('GBP', 'AUD', 1.91, datetime.now().strftime('%Y-%m-%d'), 'api', now)
        ]

        cursor.executemany('''
            INSERT INTO exchange_rates 
            (from_currency, to_currency, exchange_rate, rate_date, source, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', exchange_rates)

    # Default currency settings
    cursor.execute('SELECT COUNT(*) FROM currency_settings')
    if cursor.fetchone()[0] == 0:
        cursor.execute('''
            INSERT INTO currency_settings 
            (base_currency, auto_update_rates, rate_update_frequency, last_rate_update, created_at, updated_at)
            VALUES ('GBP', 1, 24, ?, ?, ?)
        ''', (now, now, now))

    # Default fee types
    cursor.execute('SELECT COUNT(*) FROM fee_types')
    if cursor.fetchone()[0] == 0:
        fee_types = [
            ('Tuition Fee', 'Annual tuition payment', 0, '2024-2025', 0, None, None, 0, now, now),
            ('Late Payment Fee', 'Fee for overdue payments', 0, '2024-2025', 1, 'fixed', 50.00, 7, now, now),
            ('Library Fee', 'Annual library access fee', 1, '2024-2025', 0, None, None, 0, now, now),
            ('Graduation Fee', 'One-time graduation ceremony fee', 0, '2024-2025', 0, None, None, 0, now, now)
        ]

        cursor.executemany('''
            INSERT INTO fee_types 
            (fee_name, description, is_recurring, academic_year, is_late_fee, 
             late_fee_calculation, late_fee_amount, grace_period_days, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', fee_types)

    # Sample scholarships
    cursor.execute('SELECT COUNT(*) FROM scholarships')
    if cursor.fetchone()[0] == 0:
        scholarships = [
            ('Merit Scholarship', 'Academic excellence scholarship', 2000.00, '2024-2025', 'GPA > 3.5', '2024-12-31', 1, now, now),
            ('Need-Based Grant', 'Financial need assistance', 1500.00, '2024-2025', 'Demonstrated financial need', '2024-12-31', 1, now, now),
            ('International Student Scholarship', 'Support for international students', 3000.00, '2024-2025', 'International student status', '2024-12-31', 1, now, now)
        ]

        cursor.executemany('''
            INSERT INTO scholarships 
            (scholarship_name, description, amount, academic_year, criteria, deadline, is_active, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', scholarships)

def initialize_finance(auth_instance=None):
    """Initialize the finance database with proper auth integration"""
    global auth

    print("🏦 Initializing Enhanced Finance Management System...")

    # Use provided auth instance or create/get existing one
    if auth_instance:
        auth = auth_instance
        print("✅ Using provided UserAuth instance")
    elif not auth:
        try:
            # Import and use centralized authentication system
            from university_system.infrastructure.auth import UserAuth
            auth = get_auth()
            if auth is None:
                auth = UserAuth()
            print("✅ UserAuth instance created successfully")
        except Exception as e:
            print(f"❌ Failed to initialize UserAuth: {e}")
            raise

    # Initialize database
    init_enhanced_finance_db()

    # Create sample students
    create_sample_students()

    print("✅ Finance system initialized successfully!")
    return auth

def complete_database_fix():
    """Complete database setup with all required tables and columns"""
    print("🔧 Setting up complete finance database...")

    # Remove existing problematic database
    from university_system.modules.shared.constants.paths import DEFAULT_DB_PATH
    if os.path.exists(str(DEFAULT_DB_PATH)):
        print("🗑️  Removing existing database...")
        os.remove(str(DEFAULT_DB_PATH))

    # Create new database with complete schema
    conn = get_connection()
    cursor = conn.cursor()

    print("📋 Creating complete database schema...")

    # Students table - COMPLETE with all required columns
    cursor.execute('''
    CREATE TABLE students (
        student_id TEXT PRIMARY KEY,
        first_name TEXT NOT NULL,
        last_name TEXT NOT NULL,
        email_address TEXT,
        phone_number TEXT,
        course TEXT,
        enrollment_date TEXT,
        status TEXT DEFAULT 'active',
        date_of_birth TEXT,
        address TEXT,
        emergency_contact TEXT,
        created_at TEXT,
        updated_at TEXT
    )
    ''')

    # Fee types table
    cursor.execute('''
    CREATE TABLE fee_types (
        fee_type_id INTEGER PRIMARY KEY AUTOINCREMENT,
        fee_name TEXT NOT NULL,
        description TEXT,
        is_recurring BOOLEAN DEFAULT 0,
        academic_year TEXT,
        is_late_fee BOOLEAN DEFAULT 0,
        late_fee_calculation TEXT,
        late_fee_amount DECIMAL(10,2),
        grace_period_days INTEGER DEFAULT 0,
        created_at TEXT,
        updated_at TEXT
    )
    ''')

    # Program fees table
    cursor.execute('''
    CREATE TABLE program_fees (
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

    # Student fees table
    cursor.execute('''
    CREATE TABLE student_fees (
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

    # Payments table
    cursor.execute('''
    CREATE TABLE payments (
        payment_id INTEGER PRIMARY KEY AUTOINCREMENT,
        student_id TEXT NOT NULL,
        amount DECIMAL(10,2) NOT NULL,
        currency TEXT DEFAULT 'GBP',
        payment_method TEXT,
        gateway_transaction_id TEXT,
        gateway_name TEXT,
        transaction_id TEXT,
        payment_date TEXT,
        status TEXT DEFAULT 'completed',
        notes TEXT,
        created_by TEXT,
        created_at TEXT,
        fraud_score DECIMAL(3,2),
        is_suspicious BOOLEAN DEFAULT 0,
        FOREIGN KEY (student_id) REFERENCES students (student_id)
    )
    ''')

    # Payment allocations table
    cursor.execute('''
    CREATE TABLE payment_allocations (
        allocation_id INTEGER PRIMARY KEY AUTOINCREMENT,
        payment_id INTEGER NOT NULL,
        student_fee_id INTEGER NOT NULL,
        amount DECIMAL(10,2) NOT NULL,
        created_at TEXT,
        FOREIGN KEY (payment_id) REFERENCES payments (payment_id),
        FOREIGN KEY (student_fee_id) REFERENCES student_fees (student_fee_id)
    )
    ''')

    # Payment plan templates
    cursor.execute('''
    CREATE TABLE payment_plan_templates (
        template_id INTEGER PRIMARY KEY AUTOINCREMENT,
        template_name TEXT NOT NULL,
        description TEXT,
        number_of_installments INTEGER NOT NULL,
        installment_frequency TEXT NOT NULL,
        setup_fee DECIMAL(10,2) DEFAULT 0,
        interest_rate DECIMAL(5,2) DEFAULT 0,
        early_payment_discount DECIMAL(5,2) DEFAULT 0,
        late_payment_penalty DECIMAL(5,2) DEFAULT 0,
        is_active BOOLEAN DEFAULT 1,
        created_at TEXT,
        updated_at TEXT
    )
    ''')

    # Student payment plans
    cursor.execute('''
    CREATE TABLE student_payment_plans (
        payment_plan_id INTEGER PRIMARY KEY AUTOINCREMENT,
        student_id TEXT NOT NULL,
        template_id INTEGER,
        total_amount DECIMAL(10,2) NOT NULL,
        remaining_amount DECIMAL(10,2) NOT NULL,
        currency TEXT DEFAULT 'GBP',
        status TEXT DEFAULT 'active',
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

    # Payment plan installments
    cursor.execute('''
    CREATE TABLE payment_plan_installments (
        installment_id INTEGER PRIMARY KEY AUTOINCREMENT,
        payment_plan_id INTEGER NOT NULL,
        installment_number INTEGER NOT NULL,
        amount DECIMAL(10,2) NOT NULL,
        due_date TEXT NOT NULL,
        status TEXT DEFAULT 'pending',
        payment_id INTEGER,
        late_fee_amount DECIMAL(10,2) DEFAULT 0,
        created_at TEXT,
        updated_at TEXT,
        FOREIGN KEY (payment_plan_id) REFERENCES student_payment_plans (payment_plan_id),
        FOREIGN KEY (payment_id) REFERENCES payments (payment_id)
    )
    ''')

    # Refunds table
    cursor.execute('''
    CREATE TABLE refunds (
        refund_id INTEGER PRIMARY KEY AUTOINCREMENT,
        student_id TEXT NOT NULL,
        original_payment_id INTEGER,
        refund_amount DECIMAL(10,2) NOT NULL,
        currency TEXT DEFAULT 'GBP',
        refund_reason TEXT NOT NULL,
        refund_type TEXT NOT NULL,
        refund_method TEXT,
        status TEXT DEFAULT 'pending',
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

    # Student credits table
    cursor.execute('''
    CREATE TABLE student_credits (
        credit_id INTEGER PRIMARY KEY AUTOINCREMENT,
        student_id TEXT NOT NULL,
        credit_amount DECIMAL(10,2) NOT NULL,
        currency TEXT DEFAULT 'GBP',
        credit_source TEXT,
        description TEXT,
        expiry_date TEXT,
        remaining_amount DECIMAL(10,2) NOT NULL,
        status TEXT DEFAULT 'active',
        created_by TEXT,
        created_at TEXT,
        updated_at TEXT,
        FOREIGN KEY (student_id) REFERENCES students (student_id)
    )
    ''')

    # Late fees table
    cursor.execute('''
    CREATE TABLE late_fees (
        late_fee_id INTEGER PRIMARY KEY AUTOINCREMENT,
        student_fee_id INTEGER NOT NULL,
        late_fee_amount DECIMAL(10,2) NOT NULL,
        calculation_method TEXT,
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

    # Exchange rates table
    cursor.execute('''
    CREATE TABLE exchange_rates (
        rate_id INTEGER PRIMARY KEY AUTOINCREMENT,
        from_currency TEXT NOT NULL,
        to_currency TEXT NOT NULL,
        exchange_rate DECIMAL(10,6) NOT NULL,
        rate_date TEXT NOT NULL,
        source TEXT,
        created_at TEXT
    )
    ''')

    # Currency settings table
    cursor.execute('''
    CREATE TABLE currency_settings (
        setting_id INTEGER PRIMARY KEY AUTOINCREMENT,
        base_currency TEXT DEFAULT 'GBP',
        auto_update_rates BOOLEAN DEFAULT 1,
        rate_update_frequency INTEGER DEFAULT 24,
        last_rate_update TEXT,
        created_at TEXT,
        updated_at TEXT
    )
    ''')

    # Scholarships table
    cursor.execute('''
    CREATE TABLE scholarships (
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

    # Student scholarships table
    cursor.execute('''
    CREATE TABLE student_scholarships (
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

    # Financial aid types table
    cursor.execute('''
    CREATE TABLE financial_aid_types (
        aid_type_id INTEGER PRIMARY KEY AUTOINCREMENT,
        aid_name TEXT NOT NULL,
        aid_category TEXT,
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

    # Student financial aid table
    cursor.execute('''
    CREATE TABLE student_financial_aid (
        aid_id INTEGER PRIMARY KEY AUTOINCREMENT,
        student_id TEXT NOT NULL,
        aid_type_id INTEGER NOT NULL,
        awarded_amount DECIMAL(10,2) NOT NULL,
        disbursed_amount DECIMAL(10,2) DEFAULT 0,
        remaining_amount DECIMAL(10,2) NOT NULL,
        currency TEXT DEFAULT 'GBP',
        status TEXT DEFAULT 'pending',
        application_date TEXT,
        approval_date TEXT,
        disbursement_schedule TEXT,
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

    # Budget categories table
    cursor.execute('''
    CREATE TABLE budget_categories (
        category_id INTEGER PRIMARY KEY AUTOINCREMENT,
        category_name TEXT NOT NULL,
        category_type TEXT NOT NULL,
        parent_category_id INTEGER,
        is_active BOOLEAN DEFAULT 1,
        created_at TEXT,
        updated_at TEXT,
        FOREIGN KEY (parent_category_id) REFERENCES budget_categories (category_id)
    )
    ''')

    # Budget plans table
    cursor.execute('''
    CREATE TABLE budget_plans (
        budget_id INTEGER PRIMARY KEY AUTOINCREMENT,
        plan_name TEXT NOT NULL,
        academic_year TEXT NOT NULL,
        currency TEXT DEFAULT 'GBP',
        status TEXT DEFAULT 'draft',
        total_revenue_budget DECIMAL(12,2) DEFAULT 0,
        total_expense_budget DECIMAL(12,2) DEFAULT 0,
        created_by TEXT,
        approved_by TEXT,
        notes TEXT,
        created_at TEXT,
        updated_at TEXT
    )
    ''')

    # Budget line items table
    cursor.execute('''
    CREATE TABLE budget_line_items (
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

    # Notification templates table
    cursor.execute('''
    CREATE TABLE notification_templates (
        template_id INTEGER PRIMARY KEY AUTOINCREMENT,
        template_name TEXT NOT NULL,
        template_type TEXT NOT NULL,
        subject_template TEXT NOT NULL,
        body_template TEXT NOT NULL,
        send_method TEXT DEFAULT 'email',
        is_active BOOLEAN DEFAULT 1,
        created_at TEXT,
        updated_at TEXT
    )
    ''')

    # Notification schedules table
    cursor.execute('''
    CREATE TABLE notification_schedules (
        schedule_id INTEGER PRIMARY KEY AUTOINCREMENT,
        template_id INTEGER NOT NULL,
        trigger_condition TEXT NOT NULL,
        days_before_due INTEGER,
        max_reminders INTEGER DEFAULT 3,
        reminder_interval_days INTEGER DEFAULT 7,
        is_active BOOLEAN DEFAULT 1,
        created_at TEXT,
        updated_at TEXT,
        FOREIGN KEY (template_id) REFERENCES notification_templates (template_id)
    )
    ''')

    # Sent notifications table
    cursor.execute('''
    CREATE TABLE sent_notifications (
        notification_id INTEGER PRIMARY KEY AUTOINCREMENT,
        student_id TEXT NOT NULL,
        template_id INTEGER NOT NULL,
        recipient_email TEXT,
        recipient_phone TEXT,
        subject TEXT,
        message_body TEXT,
        send_method TEXT,
        status TEXT DEFAULT 'pending',
        sent_at TEXT,
        error_message TEXT,
        created_at TEXT,
        FOREIGN KEY (student_id) REFERENCES students (student_id),
        FOREIGN KEY (template_id) REFERENCES notification_templates (template_id)
    )
    ''')

    # Financial KPIs table
    cursor.execute('''
    CREATE TABLE financial_kpis (
        kpi_id INTEGER PRIMARY KEY AUTOINCREMENT,
        kpi_name TEXT NOT NULL,
        kpi_value DECIMAL(15,2) NOT NULL,
        kpi_type TEXT NOT NULL,
        calculation_period TEXT NOT NULL,
        calculation_date TEXT NOT NULL,
        academic_year TEXT,
        created_at TEXT
    )
    ''')

    # Payment risk scores table
    cursor.execute('''
    CREATE TABLE payment_risk_scores (
        score_id INTEGER PRIMARY KEY AUTOINCREMENT,
        student_id TEXT NOT NULL,
        risk_score DECIMAL(5,2) NOT NULL,
        risk_level TEXT NOT NULL,
        factors TEXT,
        last_calculated TEXT,
        created_at TEXT,
        FOREIGN KEY (student_id) REFERENCES students (student_id)
    )
    ''')

    # Audit log table
    cursor.execute('''
    CREATE TABLE audit_log (
        log_id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id TEXT,
        action TEXT NOT NULL,
        table_name TEXT,
        record_id TEXT,
        old_values TEXT,
        new_values TEXT,
        ip_address TEXT,
        user_agent TEXT,
        session_id TEXT,
        timestamp TEXT NOT NULL
    )
    ''')

    # Collection agencies table
    cursor.execute('''
    CREATE TABLE collection_agencies (
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

    # Collection cases table
    cursor.execute('''
    CREATE TABLE collection_cases (
        case_id INTEGER PRIMARY KEY AUTOINCREMENT,
        student_id TEXT NOT NULL,
        agency_id INTEGER,
        total_debt DECIMAL(10,2) NOT NULL,
        case_status TEXT DEFAULT 'new',
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

    print("📊 Adding comprehensive sample data...")

    now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    today = datetime.now().strftime('%Y-%m-%d')

    # Add sample students with ALL required columns
    sample_students = [
        ('STU001', 'John', 'Smith', 'john.smith@university.ac.uk', '07123456789', 'Computer Science', '2024-09-01', 'active', '2002-05-15', '123 University Street, London', 'Jane Smith - 07111222333', now, now),
        ('STU002', 'Sarah', 'Johnson', 'sarah.johnson@university.ac.uk', '07123456790', 'Business Administration', '2024-09-01', 'active', '2003-08-22', '456 College Road, Manchester', 'Bob Johnson - 07444555666', now, now),
        ('STU003', 'Michael', 'Brown', 'michael.brown@university.ac.uk', '07123456791', 'Engineering', '2024-09-01', 'active', '2001-12-10', '789 Student Ave, Birmingham', 'Lisa Brown - 07777888999', now, now),
        ('STU004', 'Emma', 'Davis', 'emma.davis@university.ac.uk', '07123456792', 'Psychology', '2024-09-01', 'active', '2002-03-18', '321 Campus Drive, Leeds', 'Mark Davis - 07222333444', now, now),
        ('STU005', 'James', 'Wilson', 'james.wilson@university.ac.uk', '07123456793', 'Mathematics', '2024-09-01', 'active', '2003-11-05', '654 Education Lane, Liverpool', 'Helen Wilson - 07555666777', now, now)
    ]

    cursor.executemany('''
    INSERT INTO students 
    (student_id, first_name, last_name, email_address, phone_number, course, 
     enrollment_date, status, date_of_birth, address, emergency_contact, created_at, updated_at)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', sample_students)

    # Add comprehensive fee types
    fee_types = [
        ('Tuition Fee', 'Annual tuition payment', 0, '2024-2025', 0, None, None, 0, now, now),
        ('Registration Fee', 'One-time registration fee', 0, '2024-2025', 0, None, None, 0, now, now),
        ('Library Fee', 'Annual library access fee', 1, '2024-2025', 0, None, None, 0, now, now),
        ('Lab Fee', 'Laboratory access and materials', 1, '2024-2025', 0, None, None, 0, now, now),
        ('Graduation Fee', 'One-time graduation ceremony fee', 0, '2024-2025', 0, None, None, 0, now, now),
        ('Late Payment Fee', 'Fee for overdue payments', 0, '2024-2025', 1, 'fixed', 50.00, 7, now, now),
        ('Technology Fee', 'IT services and computer access', 1, '2024-2025', 0, None, None, 0, now, now),
        ('Student Services Fee', 'Student support services', 1, '2024-2025', 0, None, None, 0, now, now)
    ]

    cursor.executemany('''
    INSERT INTO fee_types 
    (fee_name, description, is_recurring, academic_year, is_late_fee, 
     late_fee_calculation, late_fee_amount, grace_period_days, created_at, updated_at)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', fee_types)

    # Add program fees for different courses
    program_fees = [
        (1, 'Computer Science', 9250.00, 'GBP', '2024-2025', '2024-12-01', 5.00, 30, now, now),
        (1, 'Business Administration', 8750.00, 'GBP', '2024-2025', '2024-12-01', 5.00, 30, now, now),
        (1, 'Engineering', 9500.00, 'GBP', '2024-2025', '2024-12-01', 5.00, 30, now, now),
        (1, 'Psychology', 8500.00, 'GBP', '2024-2025', '2024-12-01', 5.00, 30, now, now),
        (1, 'Mathematics', 8750.00, 'GBP', '2024-2025', '2024-12-01', 5.00, 30, now, now),
        (3, 'Computer Science', 150.00, 'GBP', '2024-2025', '2024-11-01', 0, 0, now, now),
        (3, 'Business Administration', 100.00, 'GBP', '2024-2025', '2024-11-01', 0, 0, now, now),
        (3, 'Engineering', 150.00, 'GBP', '2024-2025', '2024-11-01', 0, 0, now, now),
        (3, 'Psychology', 100.00, 'GBP', '2024-2025', '2024-11-01', 0, 0, now, now),
        (3, 'Mathematics', 100.00, 'GBP', '2024-2025', '2024-11-01', 0, 0, now, now)
    ]

    cursor.executemany('''
    INSERT INTO program_fees 
    (fee_type_id, course, amount, currency, academic_year, due_date, 
     early_payment_discount, early_payment_days, created_at, updated_at)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', program_fees)

    # Add sample student fees
    student_fees = [
        ('STU001', 1, 9250.00, 'GBP', 'unpaid', '2024-12-01', None, 0, now, now),
        ('STU001', 3, 150.00, 'GBP', 'paid', '2024-11-01', None, 0, now, now),
        ('STU002', 1, 8750.00, 'GBP', 'partial', '2024-12-01', None, 1, now, now),
        ('STU002', 3, 100.00, 'GBP', 'paid', '2024-11-01', None, 0, now, now),
        ('STU003', 1, 9500.00, 'GBP', 'unpaid', '2024-12-01', None, 0, now, now),
        ('STU003', 3, 150.00, 'GBP', 'unpaid', '2024-11-01', None, 1, now, now),
        ('STU004', 1, 8500.00, 'GBP', 'paid', '2024-12-01', None, 0, now, now),
        ('STU005', 1, 8750.00, 'GBP', 'partial', '2024-12-01', None, 0, now, now)
    ]

    cursor.executemany('''
    INSERT INTO student_fees 
    (student_id, fee_type_id, amount, currency, status, due_date, 
     last_reminder_sent, reminder_count, created_at, updated_at)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', student_fees)

    # Add sample payments
    sample_payments = [
        ('STU001', 150.00, 'GBP', 'Bank Transfer', None, None, 'TXN001', '2024-10-15', 'completed', 'Library fee payment', 'admin', now, None, 0),
        ('STU002', 4000.00, 'GBP', 'Credit Card', None, None, 'TXN002', '2024-10-20', 'completed', 'Partial tuition payment', 'admin', now, None, 0),
        ('STU002', 100.00, 'GBP', 'Cash', None, None, 'TXN003', '2024-10-25', 'completed', 'Library fee payment', 'admin', now, None, 0),
        ('STU004', 8500.00, 'GBP', 'Bank Transfer', None, None, 'TXN004', '2024-11-01', 'completed', 'Full tuition payment', 'admin', now, None, 0),
        ('STU005', 3000.00, 'GBP', 'Credit Card', None, None, 'TXN005', '2024-11-05', 'completed', 'Partial tuition payment', 'admin', now, None, 0)
    ]

    cursor.executemany('''
    INSERT INTO payments 
    (student_id, amount, currency, payment_method, gateway_transaction_id, gateway_name, 
     transaction_id, payment_date, status, notes, created_by, created_at, fraud_score, is_suspicious)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', sample_payments)

    # Add payment plan templates
    payment_plan_templates = [
        ('3-Month Plan', 'Pay fees over 3 monthly installments', 3, 'monthly', 25.00, 0.00, 5.00, 2.00, 1, now, now),
        ('6-Month Plan', 'Pay fees over 6 monthly installments', 6, 'monthly', 50.00, 1.50, 5.00, 2.00, 1, now, now),
        ('Semester Plan', 'Pay fees in 2 semester installments', 2, 'quarterly', 15.00, 0.00, 3.00, 2.50, 1, now, now),
        ('Annual Plan', 'Pay fees in yearly installments', 1, 'yearly', 0.00, 0.00, 10.00, 0.00, 1, now, now),
        ('Extended Plan', 'Pay fees over 12 monthly installments', 12, 'monthly', 100.00, 2.50, 5.00, 3.00, 1, now, now)
    ]

    cursor.executemany('''
    INSERT INTO payment_plan_templates 
    (template_name, description, number_of_installments, installment_frequency, 
     setup_fee, interest_rate, early_payment_discount, late_payment_penalty, 
     is_active, created_at, updated_at)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', payment_plan_templates)

    # Add comprehensive scholarships
    scholarships = [
        ('Merit Scholarship', 'Academic excellence scholarship for top performers', 2000.00, '2024-2025', 'GPA > 3.5 and excellent academic record', '2024-12-31', 1, now, now),
        ('Need-Based Grant', 'Financial assistance for students with demonstrated need', 1500.00, '2024-2025', 'Demonstrated financial need and good academic standing', '2024-12-31', 1, now, now),
        ('International Student Scholarship', 'Support for international students', 3000.00, '2024-2025', 'International student status with good grades', '2024-12-31', 1, now, now),
        ('STEM Excellence Award', 'For outstanding STEM students', 2500.00, '2024-2025', 'STEM field with exceptional performance', '2024-12-31', 1, now, now),
        ('Community Service Award', 'Recognizing community involvement', 1000.00, '2024-2025', 'Demonstrated community service and good grades', '2024-12-31', 1, now, now)
    ]

    cursor.executemany('''
    INSERT INTO scholarships 
    (scholarship_name, description, amount, academic_year, criteria, deadline, is_active, created_at, updated_at)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', scholarships)

    # Add financial aid types
    financial_aid_types = [
        ('Emergency Grant', 'grant', 'Short-term financial assistance for emergencies', 1000.00, 'Demonstrated emergency need and good standing', None, 0, 0, None, None, 1, now, now),
        ('Student Loan', 'loan', 'Low-interest student loan for educational expenses', 10000.00, 'Good academic standing and financial need assessment', None, 1, 1, 3.50, 6, 1, now, now),
        ('Work Study Program', 'work_study', 'Part-time employment opportunity on campus', 2000.00, 'Financial need and good academic standing', None, 1, 0, None, None, 1, now, now),
        ('Hardship Fund', 'emergency', 'Emergency financial support for unexpected difficulties', 500.00, 'Unexpected financial hardship documentation', None, 0, 0, None, None, 1, now, now),
        ('Graduate Assistance', 'grant', 'Support for graduate students', 5000.00, 'Graduate student status and research involvement', None, 1, 0, None, None, 1, now, now)
    ]

    cursor.executemany('''
    INSERT INTO financial_aid_types 
    (aid_name, aid_category, description, max_amount, eligibility_criteria, 
     application_deadline, is_renewable, requires_repayment, interest_rate, 
     grace_period_months, is_active, created_at, updated_at)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', financial_aid_types)

    # Add comprehensive budget categories
    budget_categories = [
        ('Revenue', 'revenue', None, 1, now, now),
        ('Student Fees', 'revenue', 1, 1, now, now),
        ('Government Funding', 'revenue', 1, 1, now, now),
        ('Donations & Grants', 'revenue', 1, 1, now, now),
        ('Research Funding', 'revenue', 1, 1, now, now),
        ('Expenses', 'expense', None, 1, now, now),
        ('Staff Salaries', 'expense', 6, 1, now, now),
        ('Facilities & Maintenance', 'expense', 6, 1, now, now),
        ('Technology & Equipment', 'expense', 6, 1, now, now),
        ('Student Services', 'expense', 6, 1, now, now),
        ('Marketing & Recruitment', 'expense', 6, 1, now, now),
        ('Administrative Costs', 'expense', 6, 1, now, now)
    ]

    cursor.executemany('''
    INSERT INTO budget_categories 
    (category_name, category_type, parent_category_id, is_active, created_at, updated_at)
    VALUES (?, ?, ?, ?, ?, ?)
    ''', budget_categories)

    # Add currency settings
    cursor.execute('''
    INSERT INTO currency_settings 
    (base_currency, auto_update_rates, rate_update_frequency, last_rate_update, created_at, updated_at)
    VALUES ('GBP', 1, 24, ?, ?, ?)
    ''', (now, now, now))

    # Add sample exchange rates
    exchange_rates = [
        ('GBP', 'USD', 1.27, today, 'api', now),
        ('GBP', 'EUR', 1.17, today, 'api', now),
        ('GBP', 'CAD', 1.71, today, 'api', now),
        ('GBP', 'AUD', 1.91, today, 'api', now),
        ('USD', 'GBP', 0.79, today, 'api', now),
        ('EUR', 'GBP', 0.85, today, 'api', now)
    ]

    cursor.executemany('''
    INSERT INTO exchange_rates 
    (from_currency, to_currency, exchange_rate, rate_date, source, created_at)
    VALUES (?, ?, ?, ?, ?, ?)
    ''', exchange_rates)

    # Add notification templates
    notification_templates = [
        ('Payment Reminder', 'payment_reminder', 'Payment Reminder - Fees Due Soon', 'Dear {student_name}, your payment of £{amount} is due on {due_date}. Please ensure timely payment to avoid late fees.', 'email', 1, now, now),
        ('Overdue Notice', 'overdue_notice', 'URGENT: Overdue Payment Notice', 'Dear {student_name}, your payment of £{amount} was due on {due_date} and is now overdue. Late fees may apply.', 'email', 1, now, now),
        ('Payment Confirmation', 'payment_confirmation', 'Payment Received - Thank You', 'Dear {student_name}, we confirm receipt of your payment of £{amount} on {payment_date}. Thank you!', 'email', 1, now, now),
        ('Payment Plan Setup', 'payment_plan_setup', 'Payment Plan Confirmation', 'Dear {student_name}, your payment plan has been set up successfully. Your next payment of £{amount} is due on {next_due_date}.', 'email', 1, now, now),
        ('Scholarship Award', 'scholarship_award', 'Scholarship Award Notification', 'Congratulations {student_name}! You have been awarded the {scholarship_name} worth £{amount}.', 'email', 1, now, now)
    ]

    cursor.executemany('''
    INSERT INTO notification_templates 
    (template_name, template_type, subject_template, body_template, send_method, is_active, created_at, updated_at)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    ''', notification_templates)

    conn.commit()
    conn.close()

    print("✅ Complete database setup finished successfully!")
    print("\n📊 Database Summary:")
    print(f"- 5 sample students with complete information")
    print(f"- 8 fee types including late fees")
    print(f"- 10 program fees across different courses")
    print(f"- 8 student fees with various statuses")
    print(f"- 5 sample payments")
    print(f"- 5 payment plan templates")
    print(f"- 5 scholarships")
    print(f"- 5 financial aid types")
    print(f"- 12 budget categories")
    print(f"- 6 exchange rates")
    print(f"- 5 notification templates")
    print(f"- Currency settings configured")

def verify_fix():
    """Verify that the fix worked"""
    try:
        conn = get_connection()
        cursor = conn.cursor()

        # Test each table
        tables_to_test = [
            'students', 'fee_types', 'student_fees', 'payments', 'student_credits',
            'payment_plan_templates', 'student_payment_plans', 'late_fees',
            'currency_settings', 'exchange_rates', 'scholarships', 'financial_aid_types',
            'student_financial_aid', 'notification_schedules', 'budget_plans', 'budget_categories'
        ]

        print("\n🧪 Verifying database tables...")
        all_good = True

        for table in tables_to_test:
            try:
                cursor.execute(f'SELECT COUNT(*) FROM {table}')
                count = cursor.fetchone()[0]
                print(f"✅ {table}: {count} records")
            except sqlite3.Error as e:
                print(f"❌ {table}: ERROR - {e}")
                all_good = False

        conn.close()

        if all_good:
            print("\n🎉 All tables verified successfully!")
            print("\n🚀 Your finance system is now ready to use!")
            print("\nYou can now run your finance system without database errors.")
        else:
            print("\n⚠️  Some issues remain. Check the errors above.")

        return all_good

    except Exception as e:
        print(f"❌ Verification failed: {e}")
        return False

def quick_fix_database():
    """Quick fix for database setup"""
    complete_database_fix()

def ensure_database_exists():
    """Ensure database file exists and is accessible"""
    try:
        from university_system.modules.shared.constants.paths import DEFAULT_DB_PATH
        if not os.path.exists(str(DEFAULT_DB_PATH)):
            print("🔧 Creating new database...")
            complete_database_fix()
        return True
    except Exception as e:
        print(f"❌ Database creation failed: {e}")
        return False

def check_required_packages():
    """Check if required packages are installed"""
    required_packages = ['matplotlib', 'seaborn', 'numpy', 'pandas', 'sklearn']
    missing = []

    for package in required_packages:
        try:
            __import__(package)
        except ImportError:
            missing.append(package)

    if missing:
        print(f"⚠️  Missing packages: {', '.join(missing)}")
        print(f"💡 Install with: pip install {' '.join(missing)}")
        return False
    return True
