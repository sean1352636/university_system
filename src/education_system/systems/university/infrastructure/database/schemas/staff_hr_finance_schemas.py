"""Staff HR schemas — Finance (payroll, expenses, travel, grant budgets).

Auto-grouped from the former staff_hr_schemas_all.py by domain, not by the
historical _init_staff_hr_vN_schemas sprint numbering.

Idempotent. Safe to call repeatedly: every statement is CREATE TABLE
IF NOT EXISTS / CREATE INDEX IF NOT EXISTS / INSERT OR IGNORE.
"""
from __future__ import annotations

from education_system.systems.university.infrastructure.database.db import (
    sqlite3,
    get_connection,
)
from education_system.systems.university.infrastructure.sql_safety import (
    safe_alter_table_add_column,
)


def _relax_notnull_column(cursor, table, column, create_new_sql, tmp_name, columns) -> None:
    """Idempotently drop a NOT NULL constraint on ``table.column``.

    The approver column on travel_approvals is populated later, at approval
    time, not when the pending approval rows are first created. Older live
    databases declared it NOT NULL, which broke the submit flow. This rebuilds
    the table without the NOT NULL constraint, preserving all existing rows.
    Guarded by PRAGMA table_info so it only runs when the column is still
    NOT NULL and is safe to run repeatedly.
    """
    info = cursor.execute(f"PRAGMA table_info({table})").fetchall()
    notnull = {row[1]: row[3] for row in info}
    if column not in notnull or not notnull[column]:
        return
    col_list = ", ".join(columns)
    cursor.execute(create_new_sql)
    cursor.execute(
        f"INSERT INTO {tmp_name} ({col_list}) SELECT {col_list} FROM {table}"
    )
    cursor.execute(f"DROP TABLE {table}")
    cursor.execute(f"ALTER TABLE {tmp_name} RENAME TO {table}")


def _init_finance_schemas() -> None:
    """Create every finance-domain Staff HR table."""
    try:
        with get_connection() as conn:
            cursor = conn.cursor()

            # ---- expense_categories ----
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

            # ---- expense_claims ----
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

            # ---- expense_approvals ----
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

            # ---- reimbursements ----
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

            # ---- expense_policies ----
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

            # ---- payroll_periods ----
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS payroll_periods (
                    period_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    period_type TEXT NOT NULL DEFAULT 'monthly',
                    start_date TEXT NOT NULL,
                    end_date TEXT NOT NULL,
                    payment_date TEXT,
                    status TEXT DEFAULT 'draft',
                    created_by TEXT,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
            ''')

            # ---- payroll_records ----
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS payroll_records (
                    record_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    period_id INTEGER NOT NULL,
                    user_id TEXT NOT NULL,
                    contract_id INTEGER,
                    basic_salary REAL DEFAULT 0,
                    overtime_pay REAL DEFAULT 0,
                    allowances_total REAL DEFAULT 0,
                    gross_pay REAL DEFAULT 0,
                    tax_deduction REAL DEFAULT 0,
                    ni_deduction REAL DEFAULT 0,
                    pension_deduction REAL DEFAULT 0,
                    student_loan_deduction REAL DEFAULT 0,
                    other_deductions REAL DEFAULT 0,
                    net_pay REAL DEFAULT 0,
                    payment_status TEXT DEFAULT 'pending',
                    payment_reference TEXT,
                    notes TEXT,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (period_id) REFERENCES payroll_periods(period_id)
                )
            ''')

            # ---- tax_brackets ----
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS tax_brackets (
                    bracket_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    tax_year TEXT NOT NULL,
                    bracket_name TEXT NOT NULL,
                    lower_limit REAL NOT NULL,
                    upper_limit REAL,
                    rate REAL NOT NULL,
                    personal_allowance REAL DEFAULT 0,
                    is_active INTEGER DEFAULT 1,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
            ''')

            # ---- payroll_allowances ----
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS payroll_allowances (
                    allowance_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id TEXT NOT NULL,
                    allowance_type TEXT NOT NULL,
                    amount REAL NOT NULL,
                    frequency TEXT DEFAULT 'monthly',
                    start_date TEXT NOT NULL,
                    end_date TEXT,
                    is_active INTEGER DEFAULT 1,
                    approved_by TEXT,
                    notes TEXT,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
            ''')

            # ---- payroll_overtime ----
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS payroll_overtime (
                    overtime_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id TEXT NOT NULL,
                    date TEXT NOT NULL,
                    hours REAL NOT NULL,
                    rate_multiplier REAL DEFAULT 1.5,
                    reason TEXT,
                    status TEXT DEFAULT 'pending',
                    approved_by TEXT,
                    approved_date TEXT,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
            ''')

            # ---- travel_requests ----
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS travel_requests (
                    request_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id TEXT NOT NULL,
                    purpose TEXT NOT NULL,
                    destination TEXT NOT NULL,
                    departure_date TEXT NOT NULL,
                    return_date TEXT NOT NULL,
                    estimated_budget REAL DEFAULT 0,
                    budget_breakdown_json TEXT,
                    funding_source TEXT DEFAULT 'department',
                    status TEXT DEFAULT 'draft',
                    justification TEXT,
                    department TEXT,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
            ''')

            # ---- travel_itinerary ----
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS travel_itinerary (
                    leg_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    request_id INTEGER NOT NULL,
                    leg_order INTEGER NOT NULL DEFAULT 1,
                    transport_type TEXT NOT NULL DEFAULT 'flight',
                    departure_location TEXT,
                    arrival_location TEXT,
                    departure_datetime TEXT,
                    arrival_datetime TEXT,
                    booking_reference TEXT,
                    carrier TEXT,
                    cost REAL DEFAULT 0,
                    notes TEXT,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (request_id) REFERENCES travel_requests(request_id)
                )
            ''')

            # ---- conference_registrations ----
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS conference_registrations (
                    registration_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id TEXT NOT NULL,
                    travel_request_id INTEGER,
                    conference_name TEXT NOT NULL,
                    conference_url TEXT,
                    location TEXT,
                    start_date TEXT NOT NULL,
                    end_date TEXT NOT NULL,
                    registration_fee REAL DEFAULT 0,
                    presentation_title TEXT,
                    presentation_type TEXT,
                    is_presenting INTEGER DEFAULT 0,
                    status TEXT DEFAULT 'registered',
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (travel_request_id) REFERENCES travel_requests(request_id)
                )
            ''')

            # ---- travel_approvals ----
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS travel_approvals (
                    approval_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    request_id INTEGER NOT NULL,
                    approval_level TEXT NOT NULL,
                    approver_id TEXT,
                    status TEXT DEFAULT 'pending',
                    comments TEXT,
                    reviewed_date TEXT,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (request_id) REFERENCES travel_requests(request_id)
                )
            ''')

            # ---- migration: relax NOT NULL on travel approver column ----
            # approver_id is assigned at approval time, not when the pending
            # rows are created at submit time. Self-heal legacy live databases.
            _relax_notnull_column(
                cursor, 'travel_approvals', 'approver_id',
                '''CREATE TABLE travel_approvals_new (
                    approval_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    request_id INTEGER NOT NULL,
                    approval_level TEXT NOT NULL,
                    approver_id TEXT,
                    status TEXT DEFAULT 'pending',
                    comments TEXT,
                    reviewed_date TEXT,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (request_id) REFERENCES travel_requests(request_id)
                )''',
                'travel_approvals_new',
                ['approval_id', 'request_id', 'approval_level', 'approver_id',
                 'status', 'comments', 'reviewed_date', 'created_at'],
            )

            # ---- travel_expenses ----
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS travel_expenses (
                    link_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    request_id INTEGER NOT NULL,
                    claim_id INTEGER NOT NULL,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (request_id) REFERENCES travel_requests(request_id)
                )
            ''')

            # ---- grant_budget_categories ----
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS grant_budget_categories (
                    category_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL UNIQUE,
                    description TEXT,
                    is_active INTEGER DEFAULT 1,
                    sort_order INTEGER,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
            ''')

            # ---- grant_budget_allocations ----
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS grant_budget_allocations (
                    allocation_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    grant_application_id INTEGER NOT NULL,
                    category_id INTEGER NOT NULL,
                    allocated_amount REAL DEFAULT 0,
                    spent_amount REAL DEFAULT 0,
                    committed_amount REAL DEFAULT 0,
                    remaining_amount REAL DEFAULT 0,
                    alert_threshold_pct REAL DEFAULT 80,
                    notes TEXT,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (grant_application_id) REFERENCES grant_applications(application_id),
                    FOREIGN KEY (category_id) REFERENCES grant_budget_categories(category_id)
                )
            ''')

            # ---- grant_expense_items ----
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS grant_expense_items (
                    expense_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    grant_application_id INTEGER NOT NULL,
                    allocation_id INTEGER NOT NULL,
                    category_id INTEGER NOT NULL,
                    description TEXT NOT NULL,
                    amount REAL NOT NULL,
                    expense_date TEXT,
                    vendor TEXT,
                    receipt_path TEXT,
                    invoice_number TEXT,
                    status TEXT DEFAULT 'draft',
                    submitted_by TEXT,
                    approved_by TEXT,
                    approved_date TEXT,
                    payment_reference TEXT,
                    notes TEXT,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (grant_application_id) REFERENCES grant_applications(application_id),
                    FOREIGN KEY (allocation_id) REFERENCES grant_budget_allocations(allocation_id),
                    FOREIGN KEY (category_id) REFERENCES grant_budget_categories(category_id)
                )
            ''')

            # ---- grant_funding_alerts ----
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS grant_funding_alerts (
                    alert_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    grant_application_id INTEGER NOT NULL,
                    allocation_id INTEGER,
                    alert_type TEXT DEFAULT 'threshold',
                    severity TEXT DEFAULT 'info',
                    message TEXT NOT NULL,
                    is_read INTEGER DEFAULT 0,
                    is_resolved INTEGER DEFAULT 0,
                    triggered_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    resolved_at TEXT,
                    resolved_by TEXT,
                    FOREIGN KEY (grant_application_id) REFERENCES grant_applications(application_id),
                    FOREIGN KEY (allocation_id) REFERENCES grant_budget_allocations(allocation_id)
                )
            ''')

            # ---- grant_budget_transfers ----
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS grant_budget_transfers (
                    transfer_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    grant_application_id INTEGER NOT NULL,
                    from_allocation_id INTEGER NOT NULL,
                    to_allocation_id INTEGER NOT NULL,
                    amount REAL NOT NULL,
                    reason TEXT,
                    status TEXT DEFAULT 'pending',
                    requested_by TEXT,
                    approved_by TEXT,
                    approved_date TEXT,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (grant_application_id) REFERENCES grant_applications(application_id),
                    FOREIGN KEY (from_allocation_id) REFERENCES grant_budget_allocations(allocation_id),
                    FOREIGN KEY (to_allocation_id) REFERENCES grant_budget_allocations(allocation_id)
                )
            ''')

            # ---- schema-drift migration: grant budget `updated_at` ----
            # GrantBudgetManager writes an `updated_at` timestamp on every
            # grant-budget table. Older databases predate that column on the
            # categories/transfers tables. Add it where missing so live DBs
            # self-heal. Idempotent: safe_alter_table_add_column checks
            # PRAGMA table_info and skips columns that already exist.
            for _table in (
                'grant_budget_categories',
                'grant_budget_allocations',
                'grant_expense_items',
                'grant_budget_transfers',
            ):
                try:
                    safe_alter_table_add_column(
                        _table, 'updated_at', 'TEXT', conn
                    )
                except Exception:
                    pass  # table absent or column already present

            # ---- seed default grant budget categories (owning module) ----
            # Moved here from the workload init so it runs after
            # grant_budget_categories is created.
            default_budget_cats = [
                ('Personnel', 'Salaries, benefits, and stipends', 1),
                ('Equipment', 'Research equipment and instruments', 2),
                ('Travel', 'Conference travel and fieldwork', 3),
                ('Supplies', 'Lab supplies and consumables', 4),
                ('Subcontracts', 'Subcontractor and consultant fees', 5),
                ('Publication', 'Publication and dissemination costs', 6),
                ('Indirect Costs', 'Overhead and institutional costs', 7),
                ('Other', 'Miscellaneous expenses', 8),
            ]
            for _name, _desc, _order in default_budget_cats:
                cursor.execute('''
                    INSERT OR IGNORE INTO grant_budget_categories (name, description, sort_order)
                    VALUES (?, ?, ?)
                ''', (_name, _desc, _order))

            conn.commit()
    except sqlite3.Error as exc:
        print(f"Error initialising Staff HR finance schemas: {exc}")
        raise
