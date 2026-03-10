from __future__ import annotations
from datetime import datetime
from education_system.university_system.infrastructure.database.db import get_connection, sqlite3
from education_system.university_system.core.i18n import get_text as _t, init_i18n

# Initialize i18n
init_i18n()

def init_finance_system_db():
    """Initialize the enhanced finance database with all tables"""
    try:
        conn = get_connection()
        cursor = conn.cursor()

        print(_t("schemas.initializing", name="finance system"))

        now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

        # Fee types table
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS fee_types (
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

        # Scholarships table
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

        # Student scholarships table
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

        # Payment plans table
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS payment_plan_templates (
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

        # Student finance accounts table - for student prepaid balance
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS student_finance_accounts (
            account_id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id TEXT UNIQUE NOT NULL,
            balance DECIMAL(10,2) DEFAULT 0.00,
            currency TEXT DEFAULT 'GBP',
            account_status TEXT DEFAULT 'active',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (student_id) REFERENCES students(student_id)
        )
        ''')

        # Student finance transactions table - for tracking all account transactions
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS student_finance_transactions (
            transaction_id INTEGER PRIMARY KEY AUTOINCREMENT,
            account_id INTEGER NOT NULL,
            student_id TEXT NOT NULL,
            transaction_type TEXT NOT NULL,
            amount DECIMAL(10,2) NOT NULL,
            balance_before DECIMAL(10,2),
            balance_after DECIMAL(10,2),
            description TEXT,
            reference_id TEXT,
            processed_by TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (account_id) REFERENCES student_finance_accounts(account_id),
            FOREIGN KEY (student_id) REFERENCES students(student_id)
        )
        ''')

        # Create indexes for student finance tables
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_student_finance_accounts_student ON student_finance_accounts(student_id)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_student_finance_transactions_account ON student_finance_transactions(account_id)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_student_finance_transactions_student ON student_finance_transactions(student_id)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_student_finance_transactions_date ON student_finance_transactions(created_at)')

        conn.commit()
        conn.close()
        print(_t("schemas.initialized_success", name="Finance system"))

    except sqlite3.Error as e:
        print(_t("schemas.init_error", name="finance", error=str(e)))
        if 'conn' in locals():
            conn.close()


# ============================================================================
# STUDENT UNION SCHEMAS
# ============================================================================


def init_finance_tables():
    """Initialize finance system database tables"""
    try:
        conn = get_connection()
        cursor = conn.cursor()

        print(_t("schemas.initializing", name="finance"))

        # Create budget_categories table
        cursor.execute('''
        CREATE TABLE budget_categories (
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

        # Create budget_line_items table
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

        # Create budget_plans table
        cursor.execute('''
        CREATE TABLE budget_plans (
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

        # Create club_budgets table
        cursor.execute('''
        CREATE TABLE club_budgets (
                    budget_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    club_id INTEGER,
                    fiscal_year TEXT,
                    total_budget REAL,
                    allocated_budget REAL,
                    spent_amount REAL DEFAULT 0.0,
                    category TEXT,
                    created_date TEXT,
                    updated_date TEXT,
                    FOREIGN KEY (club_id) REFERENCES student_clubs (club_id)
                )
        ''')

        # Create donations table
        cursor.execute('''
        CREATE TABLE donations (
                    donation_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    alumni_id TEXT,
                    amount REAL,
                    donation_date TEXT,
                    campaign TEXT,
                    campaign_id INTEGER,
                    payment_method TEXT,
                    is_recurring BOOLEAN,
                    recurring_frequency TEXT,
                    receipt_sent BOOLEAN,
                    notes TEXT,
                    donation_type TEXT DEFAULT 'general',
                    tribute_type TEXT,
                    tribute_name TEXT,
                    employer_match_eligible BOOLEAN DEFAULT 0,
                    employer_match_amount REAL DEFAULT 0.0,
                    recognition_level TEXT,
                    FOREIGN KEY (alumni_id) REFERENCES alumni (alumni_id),
                    FOREIGN KEY (campaign_id) REFERENCES fundraising_campaigns (campaign_id)
                )
        ''')

        # Create financial_aid_types table
        cursor.execute('''
        CREATE TABLE financial_aid_types (
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

        # Create financial_kpis table
        cursor.execute('''
        CREATE TABLE financial_kpis (
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

        # Create fundraising_donations table
        cursor.execute('''
        CREATE TABLE fundraising_donations (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        campaign_id INTEGER,
                        parent_id TEXT,
                        student_id TEXT,
                        amount DECIMAL(10,2),
                        donation_date TEXT,
                        anonymous BOOLEAN DEFAULT 0,
                        FOREIGN KEY (campaign_id) REFERENCES fundraising_campaigns (id),
                        FOREIGN KEY (parent_id) REFERENCES parent_accounts (parent_id),
                        FOREIGN KEY (student_id) REFERENCES students (student_id)
                    )
        ''')

        # Create gateway_transactions table
        cursor.execute('''
        CREATE TABLE gateway_transactions (
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

        # Create housing_payments table
        cursor.execute('''
        CREATE TABLE housing_payments (
                    payment_id TEXT PRIMARY KEY,
                    assignment_id TEXT NOT NULL,
                    student_id TEXT NOT NULL,
                    amount REAL NOT NULL,
                    payment_date TEXT NOT NULL,
                    payment_method TEXT NOT NULL,
                    transaction_reference TEXT,
                    payment_period_start TEXT NOT NULL,
                    payment_period_end TEXT NOT NULL,
                    status TEXT NOT NULL,
                    received_by TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    FOREIGN KEY (assignment_id) REFERENCES housing_assignments (assignment_id),
                    FOREIGN KEY (student_id) REFERENCES students (student_id)
                )
        ''')

        # Create late_fees table
        cursor.execute('''
        CREATE TABLE late_fees (
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

        # Create meal_transactions table
        cursor.execute('''
        CREATE TABLE meal_transactions (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        student_id TEXT,
                        transaction_type TEXT,
                        amount DECIMAL(10,2),
                        description TEXT,
                        transaction_date TEXT,
                        balance_after DECIMAL(10,2),
                        FOREIGN KEY (student_id) REFERENCES students (student_id)
                    )
        ''')

        # Create payment_gateways table
        cursor.execute('''
        CREATE TABLE payment_gateways (
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

        # Create payment_plan_installments table
        cursor.execute('''
        CREATE TABLE payment_plan_installments (
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

        # Create payment_risk_scores table
        cursor.execute('''
        CREATE TABLE payment_risk_scores (
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

        # Create refunds table
        cursor.execute('''
        CREATE TABLE refunds (
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

        # Create shop_transaction_items table
        cursor.execute('''
        CREATE TABLE shop_transaction_items (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    transaction_id TEXT NOT NULL,
                    product_id TEXT NOT NULL,
                    quantity INTEGER NOT NULL,
                    price_per_item REAL NOT NULL,
                    subtotal REAL NOT NULL,
                    FOREIGN KEY (transaction_id) REFERENCES shop_transactions (transaction_id),
                    FOREIGN KEY (product_id) REFERENCES shop_products (product_id)
                )
        ''')

        # Create shop_transactions table
        cursor.execute('''
        CREATE TABLE shop_transactions (
                    transaction_id TEXT PRIMARY KEY,
                    user_id INTEGER,
                    student_id TEXT,
                    total_amount REAL NOT NULL,
                    transaction_date TEXT NOT NULL,
                    payment_method TEXT,
                    status TEXT NOT NULL,
                    notes TEXT,
                    FOREIGN KEY (user_id) REFERENCES users (id),
                    FOREIGN KEY (student_id) REFERENCES students (student_id)
                )
        ''')

        conn.commit()
        conn.close()
        print(_t("schemas.initialized_success", name="finance"))

    except sqlite3.Error as e:
        print(_t("schemas.init_error", name="finance", error=str(e)))
        if 'conn' in locals():
            conn.close()


# ============================================================================
# HEALTH TABLES (7 tables)
# ============================================================================


