"""
Staff HR Database Schemas - Version 4

Phase 1: Core HR Expansions
- Contract & Employment Management
- Expense Claims & Reimbursements
- Grievance & Disciplinary Management
- Exit Management & Turnover Analytics

Phase 2: Academic Staff Enhancements (to be added)
Phase 3: Support Staff Features (to be added)
Phase 4: Collaboration Tools (to be added)
Phase 5: Admin System Features (to be added)
Phase 6: Academic Administration (to be added)
"""

import sqlite3
from datetime import datetime
from university_system.infrastructure.database.db import get_connection, transaction


def init_staff_hr_v4_schemas():
    """Initialize all Staff HR v4 database tables."""
    try:
        with get_connection() as conn:
            cursor = conn.cursor()

            # ==================== MIGRATION: Add missing columns ====================
            # Add status column to tables that might be missing it from earlier versions
            migration_columns = [
                ('expense_claims', 'status', "TEXT DEFAULT 'draft'"),
                ('grievances', 'status', "TEXT DEFAULT 'submitted'"),
                ('disciplinary_records', 'status', "TEXT DEFAULT 'under_review'"),
                ('staff_contracts', 'status', "TEXT DEFAULT 'active'"),
                ('exit_interviews', 'status', "TEXT DEFAULT 'scheduled'"),
            ]

            for table, column, column_def in migration_columns:
                try:
                    cursor.execute(f"ALTER TABLE {table} ADD COLUMN {column} {column_def}")
                except sqlite3.OperationalError:
                    pass  # Column already exists or table doesn't exist yet

            # ==================== CONTRACT MANAGEMENT ====================

            # Staff Contracts Table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS staff_contracts (
                    contract_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id TEXT NOT NULL,
                    contract_type TEXT NOT NULL DEFAULT 'permanent',
                    start_date TEXT NOT NULL,
                    end_date TEXT,
                    salary REAL,
                    salary_currency TEXT DEFAULT 'GBP',
                    pay_frequency TEXT DEFAULT 'monthly',
                    terms TEXT,
                    status TEXT DEFAULT 'active',
                    renewal_date TEXT,
                    probation_end_date TEXT,
                    notice_period_days INTEGER DEFAULT 30,
                    working_hours_per_week REAL DEFAULT 37.5,
                    department TEXT,
                    job_title TEXT,
                    manager_id TEXT,
                    document_path TEXT,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    created_by TEXT
                )
            ''')

            # Contract Amendments Table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS contract_amendments (
                    amendment_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    contract_id INTEGER NOT NULL,
                    change_type TEXT NOT NULL,
                    field_changed TEXT,
                    old_value TEXT,
                    new_value TEXT,
                    effective_date TEXT NOT NULL,
                    reason TEXT,
                    approved_by TEXT,
                    approved_date TEXT,
                    status TEXT DEFAULT 'pending',
                    document_path TEXT,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (contract_id) REFERENCES staff_contracts(contract_id)
                )
            ''')

            # Probation Reviews Table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS probation_reviews (
                    review_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id TEXT NOT NULL,
                    contract_id INTEGER,
                    review_date TEXT NOT NULL,
                    reviewer_id TEXT NOT NULL,
                    review_type TEXT DEFAULT 'mid-probation',
                    outcome TEXT,
                    performance_rating INTEGER,
                    strengths TEXT,
                    areas_for_improvement TEXT,
                    comments TEXT,
                    objectives_met TEXT,
                    recommendation TEXT,
                    next_review_date TEXT,
                    probation_extended BOOLEAN DEFAULT 0,
                    extension_reason TEXT,
                    extension_end_date TEXT,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (contract_id) REFERENCES staff_contracts(contract_id)
                )
            ''')

            # Contract Renewal Alerts Table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS contract_renewal_alerts (
                    alert_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    contract_id INTEGER NOT NULL,
                    alert_type TEXT NOT NULL,
                    alert_date TEXT NOT NULL,
                    days_before_expiry INTEGER,
                    sent BOOLEAN DEFAULT 0,
                    sent_date TEXT,
                    recipient_id TEXT,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (contract_id) REFERENCES staff_contracts(contract_id)
                )
            ''')

            # ==================== EXPENSE CLAIMS ====================

            # Expense Categories Table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS expense_categories (
                    category_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL UNIQUE,
                    description TEXT,
                    max_amount REAL,
                    requires_receipt BOOLEAN DEFAULT 1,
                    requires_approval BOOLEAN DEFAULT 1,
                    approval_threshold REAL,
                    is_active BOOLEAN DEFAULT 1,
                    gl_code TEXT,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
            ''')

            # Expense Claims Table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS expense_claims (
                    claim_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id TEXT NOT NULL,
                    category_id INTEGER NOT NULL,
                    amount REAL NOT NULL,
                    currency TEXT DEFAULT 'GBP',
                    description TEXT NOT NULL,
                    expense_date TEXT NOT NULL,
                    receipt_path TEXT,
                    receipt_number TEXT,
                    project_code TEXT,
                    cost_center TEXT,
                    status TEXT DEFAULT 'draft',
                    submitted_date TEXT,
                    notes TEXT,
                    mileage_miles REAL,
                    mileage_rate REAL,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (category_id) REFERENCES expense_categories(category_id)
                )
            ''')

            # Expense Approvals Table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS expense_approvals (
                    approval_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    claim_id INTEGER NOT NULL,
                    approver_id TEXT NOT NULL,
                    approval_level INTEGER DEFAULT 1,
                    decision TEXT,
                    comments TEXT,
                    decision_date TEXT,
                    amount_approved REAL,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (claim_id) REFERENCES expense_claims(claim_id)
                )
            ''')

            # Reimbursements Table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS reimbursements (
                    reimbursement_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    claim_id INTEGER NOT NULL,
                    amount REAL NOT NULL,
                    currency TEXT DEFAULT 'GBP',
                    payment_date TEXT,
                    payment_method TEXT,
                    reference_number TEXT,
                    bank_account_last4 TEXT,
                    status TEXT DEFAULT 'pending',
                    processed_by TEXT,
                    notes TEXT,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (claim_id) REFERENCES expense_claims(claim_id)
                )
            ''')

            # Expense Policies Table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS expense_policies (
                    policy_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    description TEXT,
                    max_daily_amount REAL,
                    max_single_claim REAL,
                    requires_pre_approval_above REAL,
                    mileage_rate REAL DEFAULT 0.45,
                    subsistence_rate REAL,
                    applies_to_roles TEXT,
                    effective_from TEXT,
                    effective_to TEXT,
                    is_active BOOLEAN DEFAULT 1,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
            ''')

            # ==================== GRIEVANCE & DISCIPLINARY ====================

            # Grievance Categories Table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS grievance_categories (
                    category_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL UNIQUE,
                    description TEXT,
                    severity_level INTEGER DEFAULT 1,
                    requires_investigation BOOLEAN DEFAULT 1,
                    sla_days INTEGER DEFAULT 30,
                    is_active BOOLEAN DEFAULT 1,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
            ''')

            # Grievances Table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS grievances (
                    grievance_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    reference_number TEXT UNIQUE,
                    complainant_id TEXT NOT NULL,
                    respondent_id TEXT,
                    category_id INTEGER,
                    category_other TEXT,
                    subject TEXT NOT NULL,
                    description TEXT NOT NULL,
                    is_anonymous BOOLEAN DEFAULT 0,
                    is_confidential BOOLEAN DEFAULT 1,
                    status TEXT DEFAULT 'submitted',
                    priority TEXT DEFAULT 'normal',
                    assigned_to TEXT,
                    filed_date TEXT NOT NULL,
                    acknowledged_date TEXT,
                    investigation_start_date TEXT,
                    resolution_date TEXT,
                    resolution_type TEXT,
                    resolution_summary TEXT,
                    outcome TEXT,
                    appeal_deadline TEXT,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (category_id) REFERENCES grievance_categories(category_id)
                )
            ''')

            # Grievance Actions Table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS grievance_actions (
                    action_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    grievance_id INTEGER NOT NULL,
                    action_type TEXT NOT NULL,
                    action_date TEXT NOT NULL,
                    taken_by TEXT NOT NULL,
                    details TEXT,
                    outcome TEXT,
                    next_action TEXT,
                    next_action_date TEXT,
                    documents_path TEXT,
                    is_visible_to_complainant BOOLEAN DEFAULT 1,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (grievance_id) REFERENCES grievances(grievance_id)
                )
            ''')

            # Grievance Meetings Table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS grievance_meetings (
                    meeting_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    grievance_id INTEGER NOT NULL,
                    meeting_date TEXT NOT NULL,
                    meeting_time TEXT,
                    location TEXT,
                    attendees TEXT,
                    purpose TEXT,
                    minutes TEXT,
                    outcomes TEXT,
                    follow_up_actions TEXT,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (grievance_id) REFERENCES grievances(grievance_id)
                )
            ''')

            # Disciplinary Records Table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS disciplinary_records (
                    record_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    reference_number TEXT UNIQUE,
                    user_id TEXT NOT NULL,
                    offense_type TEXT NOT NULL,
                    offense_category TEXT,
                    severity TEXT DEFAULT 'minor',
                    description TEXT NOT NULL,
                    date_occurred TEXT NOT NULL,
                    date_reported TEXT,
                    reported_by TEXT,
                    witnesses TEXT,
                    evidence_path TEXT,
                    status TEXT DEFAULT 'under_review',
                    investigation_notes TEXT,
                    is_confidential BOOLEAN DEFAULT 1,
                    previous_warnings INTEGER DEFAULT 0,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
            ''')

            # Disciplinary Actions Table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS disciplinary_actions (
                    action_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    record_id INTEGER NOT NULL,
                    action_type TEXT NOT NULL,
                    action_level TEXT,
                    effective_date TEXT NOT NULL,
                    end_date TEXT,
                    duration_days INTEGER,
                    imposed_by TEXT NOT NULL,
                    reason TEXT,
                    conditions TEXT,
                    appeal_deadline TEXT,
                    appeal_submitted BOOLEAN DEFAULT 0,
                    appeal_outcome TEXT,
                    document_path TEXT,
                    acknowledged_by_employee BOOLEAN DEFAULT 0,
                    acknowledged_date TEXT,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (record_id) REFERENCES disciplinary_records(record_id)
                )
            ''')

            # Disciplinary Appeals Table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS disciplinary_appeals (
                    appeal_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    action_id INTEGER NOT NULL,
                    appellant_id TEXT NOT NULL,
                    appeal_date TEXT NOT NULL,
                    grounds TEXT NOT NULL,
                    supporting_documents TEXT,
                    status TEXT DEFAULT 'submitted',
                    hearing_date TEXT,
                    panel_members TEXT,
                    outcome TEXT,
                    outcome_date TEXT,
                    outcome_details TEXT,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (action_id) REFERENCES disciplinary_actions(action_id)
                )
            ''')

            # ==================== EXIT MANAGEMENT ====================

            # Exit Interviews Table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS exit_interviews (
                    interview_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id TEXT NOT NULL,
                    interviewer_id TEXT,
                    scheduled_date TEXT,
                    interview_date TEXT,
                    interview_method TEXT DEFAULT 'in_person',
                    status TEXT DEFAULT 'scheduled',
                    last_working_day TEXT,
                    tenure_months INTEGER,
                    department TEXT,
                    job_title TEXT,
                    manager_id TEXT,
                    reason_for_leaving TEXT,
                    reason_category TEXT,
                    destination TEXT,
                    new_employer TEXT,
                    new_role TEXT,
                    salary_factor BOOLEAN DEFAULT 0,
                    career_growth_factor BOOLEAN DEFAULT 0,
                    work_life_balance_factor BOOLEAN DEFAULT 0,
                    management_factor BOOLEAN DEFAULT 0,
                    culture_factor BOOLEAN DEFAULT 0,
                    job_satisfaction_rating INTEGER,
                    manager_rating INTEGER,
                    work_environment_rating INTEGER,
                    growth_opportunities_rating INTEGER,
                    compensation_rating INTEGER,
                    overall_rating INTEGER,
                    liked_most TEXT,
                    liked_least TEXT,
                    suggestions TEXT,
                    would_recommend BOOLEAN,
                    would_return BOOLEAN,
                    additional_comments TEXT,
                    confidential_notes TEXT,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
            ''')

            # Exit Checklist Templates Table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS exit_checklist_templates (
                    template_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    description TEXT,
                    department TEXT,
                    role_type TEXT,
                    is_default BOOLEAN DEFAULT 0,
                    is_active BOOLEAN DEFAULT 1,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
            ''')

            # Exit Checklist Template Items Table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS exit_checklist_template_items (
                    item_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    template_id INTEGER NOT NULL,
                    task_name TEXT NOT NULL,
                    description TEXT,
                    responsible_party TEXT,
                    category TEXT,
                    days_before_exit INTEGER DEFAULT 0,
                    is_mandatory BOOLEAN DEFAULT 1,
                    order_index INTEGER DEFAULT 0,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (template_id) REFERENCES exit_checklist_templates(template_id)
                )
            ''')

            # Exit Checklist (User-specific) Table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS exit_checklist (
                    checklist_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id TEXT NOT NULL,
                    template_id INTEGER,
                    task_name TEXT NOT NULL,
                    description TEXT,
                    category TEXT,
                    responsible_party TEXT,
                    due_date TEXT,
                    completed BOOLEAN DEFAULT 0,
                    completed_date TEXT,
                    completed_by TEXT,
                    notes TEXT,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (template_id) REFERENCES exit_checklist_templates(template_id)
                )
            ''')

            # Knowledge Transfer Table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS knowledge_transfer (
                    transfer_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    departing_user_id TEXT NOT NULL,
                    receiving_user_id TEXT,
                    topic TEXT NOT NULL,
                    description TEXT,
                    documentation_path TEXT,
                    priority TEXT DEFAULT 'medium',
                    status TEXT DEFAULT 'pending',
                    scheduled_date TEXT,
                    completed_date TEXT,
                    notes TEXT,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
            ''')

            # Turnover Analytics Table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS turnover_analytics (
                    record_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    department TEXT,
                    period_start TEXT NOT NULL,
                    period_end TEXT NOT NULL,
                    period_type TEXT DEFAULT 'monthly',
                    headcount_start INTEGER DEFAULT 0,
                    headcount_end INTEGER DEFAULT 0,
                    voluntary_exits INTEGER DEFAULT 0,
                    involuntary_exits INTEGER DEFAULT 0,
                    retirements INTEGER DEFAULT 0,
                    transfers_out INTEGER DEFAULT 0,
                    new_hires INTEGER DEFAULT 0,
                    transfers_in INTEGER DEFAULT 0,
                    turnover_rate REAL,
                    retention_rate REAL,
                    avg_tenure_months REAL,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
            ''')

            # Exit Reasons Summary Table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS exit_reasons_summary (
                    summary_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    period TEXT NOT NULL,
                    department TEXT,
                    reason_category TEXT NOT NULL,
                    count INTEGER DEFAULT 0,
                    percentage REAL,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
            ''')

            conn.commit()

            # Create indexes for better performance
            _create_v4_indexes(cursor)
            conn.commit()

            # Insert default data
            _insert_v4_defaults(cursor)
            conn.commit()

            print("Staff HR v4 database schemas initialized successfully")
            return True

    except sqlite3.Error as e:
        print(f"Error initializing Staff HR v4 database: {e}")
        return False


def _create_v4_indexes(cursor):
    """Create indexes for v4 tables."""
    indexes = [
        # Contract indexes
        ('idx_contracts_user', 'staff_contracts', 'user_id'),
        ('idx_contracts_status', 'staff_contracts', 'status'),
        ('idx_contracts_end_date', 'staff_contracts', 'end_date'),
        ('idx_contracts_renewal', 'staff_contracts', 'renewal_date'),
        ('idx_amendments_contract', 'contract_amendments', 'contract_id'),
        ('idx_probation_user', 'probation_reviews', 'user_id'),

        # Expense indexes
        ('idx_expenses_user', 'expense_claims', 'user_id'),
        ('idx_expenses_status', 'expense_claims', 'status'),
        ('idx_expenses_date', 'expense_claims', 'expense_date'),
        ('idx_expense_approvals_claim', 'expense_approvals', 'claim_id'),
        ('idx_reimbursements_claim', 'reimbursements', 'claim_id'),

        # Grievance indexes
        ('idx_grievances_complainant', 'grievances', 'complainant_id'),
        ('idx_grievances_status', 'grievances', 'status'),
        ('idx_grievances_assigned', 'grievances', 'assigned_to'),
        ('idx_grievance_actions_grievance', 'grievance_actions', 'grievance_id'),

        # Disciplinary indexes
        ('idx_disciplinary_user', 'disciplinary_records', 'user_id'),
        ('idx_disciplinary_status', 'disciplinary_records', 'status'),
        ('idx_disciplinary_actions_record', 'disciplinary_actions', 'record_id'),

        # Exit indexes
        ('idx_exit_interviews_user', 'exit_interviews', 'user_id'),
        ('idx_exit_checklist_user', 'exit_checklist', 'user_id'),
        ('idx_turnover_period', 'turnover_analytics', 'period_start, period_end'),
    ]

    for idx_name, table, columns in indexes:
        try:
            cursor.execute(f'CREATE INDEX IF NOT EXISTS {idx_name} ON {table}({columns})')
        except sqlite3.Error:
            pass  # Index may already exist


def _insert_v4_defaults(cursor):
    """Insert default data for v4 tables."""

    # Default expense categories
    expense_categories = [
        ('Travel - Domestic', 'Domestic travel expenses including flights, trains, buses', 500.00, 1, 1),
        ('Travel - International', 'International travel expenses', 2000.00, 1, 1),
        ('Accommodation', 'Hotel and lodging expenses', 200.00, 1, 1),
        ('Meals & Subsistence', 'Food and drink while working away', 50.00, 1, 1),
        ('Mileage', 'Personal vehicle mileage reimbursement', None, 0, 1),
        ('Office Supplies', 'Stationery and office equipment', 100.00, 1, 1),
        ('Training & Development', 'Course fees, books, materials', 500.00, 1, 1),
        ('Conference Fees', 'Registration fees for conferences', 1000.00, 1, 1),
        ('Equipment', 'Work-related equipment purchases', 500.00, 1, 1),
        ('Software & Subscriptions', 'Software licenses and subscriptions', 200.00, 1, 1),
        ('Communication', 'Phone, internet, postage', 50.00, 1, 1),
        ('Professional Memberships', 'Professional body membership fees', 300.00, 1, 1),
        ('Other', 'Miscellaneous expenses', 100.00, 1, 1),
    ]

    for name, desc, max_amt, req_receipt, req_approval in expense_categories:
        try:
            cursor.execute('''
                INSERT OR IGNORE INTO expense_categories
                (name, description, max_amount, requires_receipt, requires_approval)
                VALUES (?, ?, ?, ?, ?)
            ''', (name, desc, max_amt, req_receipt, req_approval))
        except sqlite3.Error:
            pass

    # Default grievance categories
    grievance_categories = [
        ('Harassment', 'Workplace harassment including verbal, physical, or psychological', 3, 1, 14),
        ('Discrimination', 'Discrimination based on protected characteristics', 3, 1, 14),
        ('Bullying', 'Workplace bullying and intimidation', 3, 1, 14),
        ('Unfair Treatment', 'Perceived unfair treatment by management or colleagues', 2, 1, 21),
        ('Workload', 'Excessive or unreasonable workload issues', 1, 0, 30),
        ('Working Conditions', 'Health, safety, or environmental concerns', 2, 1, 21),
        ('Pay & Benefits', 'Issues related to compensation and benefits', 1, 0, 30),
        ('Policy Violation', 'Alleged violation of company policies', 2, 1, 21),
        ('Management Practices', 'Concerns about management decisions or practices', 1, 0, 30),
        ('Interpersonal Conflict', 'Conflicts with colleagues', 1, 0, 30),
        ('Other', 'Other grievances not covered above', 1, 0, 30),
    ]

    for name, desc, severity, req_inv, sla in grievance_categories:
        try:
            cursor.execute('''
                INSERT OR IGNORE INTO grievance_categories
                (name, description, severity_level, requires_investigation, sla_days)
                VALUES (?, ?, ?, ?, ?)
            ''', (name, desc, severity, req_inv, sla))
        except sqlite3.Error:
            pass

    # Default exit checklist template
    try:
        cursor.execute('''
            INSERT OR IGNORE INTO exit_checklist_templates
            (template_id, name, description, is_default, is_active)
            VALUES (1, 'Standard Exit Checklist', 'Default checklist for all departing employees', 1, 1)
        ''')
    except sqlite3.Error:
        pass

    # Default exit checklist items
    exit_items = [
        (1, 'Submit resignation letter', 'HR', 'Documentation', -14, 1, 1),
        (1, 'Schedule exit interview', 'HR', 'HR Process', -7, 1, 2),
        (1, 'Complete knowledge transfer', 'Manager', 'Handover', -7, 1, 3),
        (1, 'Return laptop and equipment', 'IT', 'Equipment', 0, 1, 4),
        (1, 'Return access cards and keys', 'Security', 'Access', 0, 1, 5),
        (1, 'Clear personal belongings', 'Employee', 'Personal', 0, 0, 6),
        (1, 'Settle expense claims', 'Finance', 'Finance', -3, 1, 7),
        (1, 'Update project documentation', 'Employee', 'Handover', -5, 1, 8),
        (1, 'Disable system access', 'IT', 'Access', 0, 1, 9),
        (1, 'Final paycheck processing', 'Payroll', 'Finance', 0, 1, 10),
        (1, 'Provide employment reference letter', 'HR', 'Documentation', 0, 0, 11),
        (1, 'COBRA/benefits continuation info', 'HR', 'Benefits', 0, 1, 12),
    ]

    for template_id, task, responsible, category, days_before, mandatory, order_idx in exit_items:
        try:
            cursor.execute('''
                INSERT OR IGNORE INTO exit_checklist_template_items
                (template_id, task_name, responsible_party, category,
                 days_before_exit, is_mandatory, order_index)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (template_id, task, responsible, category, days_before, mandatory, order_idx))
        except sqlite3.Error:
            pass

    # Default expense policy
    try:
        cursor.execute('''
            INSERT OR IGNORE INTO expense_policies
            (policy_id, name, description, max_daily_amount, max_single_claim,
             requires_pre_approval_above, mileage_rate, is_active)
            VALUES (1, 'Standard Expense Policy', 'Default expense policy for all staff',
                    150.00, 1000.00, 500.00, 0.45, 1)
        ''')
    except sqlite3.Error:
        pass


# Make schema initialization available
__all__ = ['init_staff_hr_v4_schemas']
