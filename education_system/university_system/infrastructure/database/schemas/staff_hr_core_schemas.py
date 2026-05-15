"""Staff HR schemas — Core (lifecycle: leave, time, training, appraisals, profiles, documents, onboarding, contracts, exit).

Auto-grouped from the former staff_hr_schemas_all.py by domain, not by the
historical _init_staff_hr_vN_schemas sprint numbering.

Idempotent. Safe to call repeatedly: every statement is CREATE TABLE
IF NOT EXISTS / CREATE INDEX IF NOT EXISTS / INSERT OR IGNORE.
"""
from __future__ import annotations

from education_system.university_system.infrastructure.database.db import (
    sqlite3,
    get_connection,
)
from education_system.university_system.core.sql_safety import (
    safe_alter_table_add_column,
)


def _init_core_schemas() -> None:
    """Create every core-domain Staff HR table."""
    try:
        with get_connection() as conn:
            cursor = conn.cursor()

            # ---- leave_types ----
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS leave_types (
                    leave_type_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL UNIQUE,
                    description TEXT,
                    max_days_per_year INTEGER DEFAULT 0,
                    requires_approval BOOLEAN DEFAULT 1,
                    is_paid BOOLEAN DEFAULT 1,
                    color_code TEXT DEFAULT '#3498db',
                    is_active BOOLEAN DEFAULT 1,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
            ''')

            # ---- leave_requests ----
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS leave_requests (
                    request_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id TEXT NOT NULL,
                    leave_type_id INTEGER NOT NULL,
                    start_date TEXT NOT NULL,
                    end_date TEXT NOT NULL,
                    total_days REAL NOT NULL,
                    reason TEXT,
                    document_path TEXT,
                    status TEXT DEFAULT 'pending',
                    approved_by TEXT,
                    approved_date TEXT,
                    rejection_reason TEXT,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (leave_type_id) REFERENCES leave_types(leave_type_id)
                )
            ''')

            # ---- leave_balances ----
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS leave_balances (
                    balance_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id TEXT NOT NULL,
                    leave_type_id INTEGER NOT NULL,
                    year INTEGER NOT NULL,
                    allocated_days REAL DEFAULT 0,
                    used_days REAL DEFAULT 0,
                    carried_over REAL DEFAULT 0,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(user_id, leave_type_id, year),
                    FOREIGN KEY (leave_type_id) REFERENCES leave_types(leave_type_id)
                )
            ''')

            # ---- time_entries ----
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS time_entries (
                    entry_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id TEXT NOT NULL,
                    entry_date TEXT NOT NULL,
                    clock_in TEXT NOT NULL,
                    clock_out TEXT,
                    break_minutes INTEGER DEFAULT 0,
                    work_type TEXT DEFAULT 'regular',
                    location TEXT DEFAULT 'office',
                    notes TEXT,
                    is_manual BOOLEAN DEFAULT 0,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
            ''')

            # ---- timesheets ----
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS timesheets (
                    timesheet_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id TEXT NOT NULL,
                    week_start TEXT NOT NULL,
                    week_end TEXT NOT NULL,
                    total_hours REAL DEFAULT 0,
                    regular_hours REAL DEFAULT 0,
                    overtime_hours REAL DEFAULT 0,
                    status TEXT DEFAULT 'draft',
                    submitted_date TEXT,
                    approved_by TEXT,
                    approved_date TEXT,
                    rejection_reason TEXT,
                    notes TEXT,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(user_id, week_start)
                )
            ''')

            # ---- training_courses ----
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS training_courses (
                    course_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    description TEXT,
                    category TEXT,
                    provider TEXT,
                    duration_hours REAL,
                    passing_score REAL DEFAULT 70,
                    is_mandatory BOOLEAN DEFAULT 0,
                    recertification_months INTEGER,
                    is_active BOOLEAN DEFAULT 1,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
            ''')

            # ---- training_enrollments ----
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS training_enrollments (
                    enrollment_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id TEXT NOT NULL,
                    course_id INTEGER NOT NULL,
                    enrolled_date TEXT DEFAULT CURRENT_TIMESTAMP,
                    due_date TEXT,
                    started_date TEXT,
                    completed_date TEXT,
                    status TEXT DEFAULT 'enrolled',
                    score REAL,
                    attempts INTEGER DEFAULT 0,
                    certificate_path TEXT,
                    notes TEXT,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (course_id) REFERENCES training_courses(course_id)
                )
            ''')

            # ---- certifications ----
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS certifications (
                    cert_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id TEXT NOT NULL,
                    name TEXT NOT NULL,
                    issuing_body TEXT,
                    credential_id TEXT,
                    issue_date TEXT,
                    expiry_date TEXT,
                    document_path TEXT,
                    status TEXT DEFAULT 'active',
                    reminder_sent BOOLEAN DEFAULT 0,
                    notes TEXT,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
            ''')

            # ---- appraisal_cycles ----
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS appraisal_cycles (
                    cycle_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    description TEXT,
                    start_date TEXT NOT NULL,
                    end_date TEXT NOT NULL,
                    self_review_deadline TEXT,
                    manager_review_deadline TEXT,
                    status TEXT DEFAULT 'draft',
                    created_by TEXT,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
            ''')

            # ---- appraisal_records ----
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS appraisal_records (
                    appraisal_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    cycle_id INTEGER NOT NULL,
                    user_id TEXT NOT NULL,
                    reviewer_id TEXT,
                    self_rating REAL,
                    manager_rating REAL,
                    final_rating REAL,
                    self_comments TEXT,
                    manager_comments TEXT,
                    strengths TEXT,
                    areas_for_improvement TEXT,
                    development_plan TEXT,
                    status TEXT DEFAULT 'pending',
                    self_submitted_date TEXT,
                    manager_submitted_date TEXT,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (cycle_id) REFERENCES appraisal_cycles(cycle_id),
                    UNIQUE(cycle_id, user_id)
                )
            ''')

            # ---- appraisal_goals ----
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS appraisal_goals (
                    goal_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id TEXT NOT NULL,
                    cycle_id INTEGER,
                    title TEXT NOT NULL,
                    description TEXT,
                    category TEXT DEFAULT 'performance',
                    target_date TEXT,
                    progress INTEGER DEFAULT 0,
                    weight REAL DEFAULT 1.0,
                    status TEXT DEFAULT 'active',
                    completion_notes TEXT,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (cycle_id) REFERENCES appraisal_cycles(cycle_id)
                )
            ''')

            # ---- onboarding_templates ----
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS onboarding_templates (
                    template_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    description TEXT,
                    role TEXT,
                    department TEXT,
                    template_type TEXT DEFAULT 'onboarding',
                    estimated_days INTEGER DEFAULT 30,
                    is_active BOOLEAN DEFAULT 1,
                    created_by TEXT,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
            ''')

            # ---- onboarding_template_tasks ----
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS onboarding_template_tasks (
                    task_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    template_id INTEGER NOT NULL,
                    title TEXT NOT NULL,
                    description TEXT,
                    category TEXT DEFAULT 'general',
                    assigned_to_role TEXT DEFAULT 'employee',
                    due_days INTEGER DEFAULT 0,
                    is_required BOOLEAN DEFAULT 1,
                    order_num INTEGER DEFAULT 0,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (template_id) REFERENCES onboarding_templates(template_id)
                )
            ''')

            # ---- onboarding_assignments ----
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS onboarding_assignments (
                    assignment_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id TEXT NOT NULL,
                    template_id INTEGER NOT NULL,
                    assigned_by TEXT,
                    start_date TEXT NOT NULL,
                    target_completion_date TEXT,
                    actual_completion_date TEXT,
                    status TEXT DEFAULT 'in_progress',
                    notes TEXT,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (template_id) REFERENCES onboarding_templates(template_id)
                )
            ''')

            # ---- onboarding_task_progress ----
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS onboarding_task_progress (
                    progress_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    assignment_id INTEGER NOT NULL,
                    task_id INTEGER NOT NULL,
                    status TEXT DEFAULT 'pending',
                    assigned_to TEXT,
                    due_date TEXT,
                    completed_by TEXT,
                    completed_date TEXT,
                    notes TEXT,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (assignment_id) REFERENCES onboarding_assignments(assignment_id),
                    FOREIGN KEY (task_id) REFERENCES onboarding_template_tasks(task_id),
                    UNIQUE(assignment_id, task_id)
                )
            ''')

            # ---- leave_requests ----
            cursor.execute('''
                CREATE INDEX IF NOT EXISTS idx_leave_requests_user
                ON leave_requests(user_id)
            ''')

            cursor.execute('''
                CREATE INDEX IF NOT EXISTS idx_leave_requests_status
                ON leave_requests(status)
            ''')

            # ---- leave_balances ----
            cursor.execute('''
                CREATE INDEX IF NOT EXISTS idx_leave_balances_user
                ON leave_balances(user_id)
            ''')

            # ---- time_entries ----
            cursor.execute('''
                CREATE INDEX IF NOT EXISTS idx_time_entries_user
                ON time_entries(user_id)
            ''')

            cursor.execute('''
                CREATE INDEX IF NOT EXISTS idx_time_entries_date
                ON time_entries(entry_date)
            ''')

            # ---- timesheets ----
            cursor.execute('''
                CREATE INDEX IF NOT EXISTS idx_timesheets_user
                ON timesheets(user_id)
            ''')

            # ---- training_enrollments ----
            cursor.execute('''
                CREATE INDEX IF NOT EXISTS idx_training_enrollments_user
                ON training_enrollments(user_id)
            ''')

            # ---- certifications ----
            cursor.execute('''
                CREATE INDEX IF NOT EXISTS idx_certifications_user
                ON certifications(user_id)
            ''')

            cursor.execute('''
                CREATE INDEX IF NOT EXISTS idx_certifications_expiry
                ON certifications(expiry_date)
            ''')

            # ---- appraisal_records ----
            cursor.execute('''
                CREATE INDEX IF NOT EXISTS idx_appraisal_records_user
                ON appraisal_records(user_id)
            ''')

            # ---- appraisal_goals ----
            cursor.execute('''
                CREATE INDEX IF NOT EXISTS idx_appraisal_goals_user
                ON appraisal_goals(user_id)
            ''')

            # ---- onboarding_assignments ----
            cursor.execute('''
                CREATE INDEX IF NOT EXISTS idx_onboarding_assignments_user
                ON onboarding_assignments(user_id)
            ''')

            # ---- onboarding_task_progress ----
            cursor.execute('''
                CREATE INDEX IF NOT EXISTS idx_onboarding_task_progress_assignment
                ON onboarding_task_progress(assignment_id)
            ''')

            default_types = [
                ('Annual Leave', 'Paid annual vacation leave', 25, 1, 1, '#27ae60'),
                ('Sick Leave', 'Leave for illness or medical appointments', 10, 1, 1, '#e74c3c'),
                ('Personal Leave', 'Leave for personal matters', 5, 1, 1, '#3498db'),
                ('Bereavement', 'Leave for family bereavement', 5, 0, 1, '#7f8c8d'),
                ('Parental Leave', 'Maternity/Paternity leave', 90, 1, 1, '#9b59b6'),
                ('Study Leave', 'Leave for educational purposes', 10, 1, 0, '#f39c12'),
                ('Unpaid Leave', 'Unpaid leave of absence', 30, 1, 0, '#95a5a6'),
                ('Emergency Leave', 'Emergency situations', 3, 0, 1, '#c0392b'),
            ]

            for leave_type in default_types:
                cursor.execute('''
                    INSERT OR IGNORE INTO leave_types
                    (name, description, max_days_per_year, requires_approval, is_paid, color_code)
                    VALUES (?, ?, ?, ?, ?, ?)
                ''', leave_type)

            cursor = conn.cursor()

            # ---- staff_profiles ----
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS staff_profiles (
                    profile_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id TEXT UNIQUE NOT NULL,
                    employee_id TEXT UNIQUE,
                    department TEXT,
                    job_title TEXT,
                    employment_type TEXT DEFAULT 'full-time',
                    hire_date TEXT,
                    contract_end_date TEXT,
                    manager_id TEXT,
                    office_location TEXT,
                    phone_extension TEXT,
                    emergency_contact_name TEXT,
                    emergency_contact_phone TEXT,
                    emergency_contact_relationship TEXT,
                    bio TEXT,
                    expertise_areas TEXT,
                    qualifications TEXT,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
            ''')

            # ---- documents ----
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS documents (
                    document_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    source_type TEXT NOT NULL DEFAULT 'general',
                    source_document_id INTEGER,
                    owner_id TEXT,
                    owner_type TEXT,
                    reference_type TEXT,
                    reference_id TEXT,
                    document_type TEXT,
                    document_name TEXT,
                    file_path TEXT,
                    file_content TEXT,
                    file_size INTEGER,
                    file_hash TEXT,
                    original_filename TEXT,
                    upload_date TEXT,
                    expiry_date TEXT,
                    issue_date TEXT,
                    status TEXT DEFAULT 'active',
                    verification_status TEXT,
                    verification_date TEXT,
                    verification_notes TEXT,
                    verified_by TEXT,
                    version_number INTEGER DEFAULT 1,
                    parent_document_id INTEGER,
                    is_current_version INTEGER DEFAULT 1,
                    workflow_status TEXT,
                    priority INTEGER,
                    tags TEXT,
                    notes TEXT,
                    uploaded_by TEXT,
                    created_at TEXT DEFAULT (datetime('now')),
                    updated_at TEXT
                )
            ''')

            # ---- document_approvals ----
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS document_approvals (
                    approval_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    document_type TEXT NOT NULL,
                    document_title TEXT,
                    document_description TEXT,
                    document_path TEXT,
                    submitted_by TEXT NOT NULL,
                    submitted_by_name TEXT,
                    submitted_date TEXT DEFAULT CURRENT_TIMESTAMP,
                    current_approver TEXT,
                    approval_chain TEXT,
                    current_step INTEGER DEFAULT 1,
                    total_steps INTEGER DEFAULT 1,
                    status TEXT DEFAULT 'pending',
                    comments TEXT,
                    completed_date TEXT,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
            ''')

            # ---- document_approval_history ----
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS document_approval_history (
                    history_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    approval_id INTEGER NOT NULL,
                    approver_id TEXT NOT NULL,
                    approver_name TEXT,
                    action TEXT,
                    step_number INTEGER,
                    comments TEXT,
                    action_date TEXT DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (approval_id) REFERENCES document_approvals(approval_id)
                )
            ''')

            # ---- staff_profiles ----
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_staff_profiles_user ON staff_profiles(user_id)')

            cursor.execute('CREATE INDEX IF NOT EXISTS idx_staff_profiles_dept ON staff_profiles(department)')

            # ---- documents ----
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_documents_owner ON documents(owner_id, owner_type)')

            # ---- document_approvals ----
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_doc_approvals_status ON document_approvals(status)')

            # ---- staff_contracts ----
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

            # ---- contract_amendments ----
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

            # ---- probation_reviews ----
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

            # ---- contract_renewal_alerts ----
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

            # ---- exit_interviews ----
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

            # ---- exit_checklist_templates ----
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

            # ---- exit_checklist_template_items ----
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

            # ---- exit_checklist ----
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

            # ---- knowledge_transfer ----
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

            # ---- turnover_analytics ----
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

            # ---- exit_reasons_summary ----
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

            # ---- exit_checklist_templates ----
            try:
                cursor.execute('''
                    INSERT OR IGNORE INTO exit_checklist_templates
                    (template_id, name, description, is_default, is_active)
                    VALUES (1, 'Standard Exit Checklist', 'Default checklist for all departing employees', 1, 1)
                ''')
            except sqlite3.Error:
                pass

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

            conn.commit()
    except sqlite3.Error as exc:
        print(f"Error initialising Staff HR core schemas: {exc}")
        raise


def get_employment_types():
    """Get list of employment types."""
    return ['full-time', 'part-time', 'contract', 'temporary', 'visiting', 'emeritus']
