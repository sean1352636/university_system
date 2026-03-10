"""
Database schema for Integrated Financial Aid & Scholarship Management
"""

FINANCIAL_AID_SCHEMA = """
-- Financial Aid Applications
CREATE TABLE IF NOT EXISTS financial_aid_applications (
    application_id INTEGER PRIMARY KEY AUTOINCREMENT,
    student_id INTEGER NOT NULL,
    academic_year TEXT NOT NULL,
    application_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    status TEXT DEFAULT 'pending',  -- pending, under_review, approved, denied
    family_income REAL,
    household_size INTEGER,
    special_circumstances TEXT,
    submitted_by INTEGER,
    reviewed_by INTEGER,
    review_date TIMESTAMP,
    review_notes TEXT,
    FOREIGN KEY (student_id) REFERENCES students(student_id)
);

-- FAFSA Data
CREATE TABLE IF NOT EXISTS fafsa_data (
    fafsa_id INTEGER PRIMARY KEY AUTOINCREMENT,
    student_id INTEGER NOT NULL,
    academic_year TEXT NOT NULL,
    efc INTEGER,  -- Expected Family Contribution
    submission_date DATE,
    processed_date DATE,
    sai INTEGER,  -- Student Aid Index (new FAFSA metric)
    dependency_status TEXT,  -- dependent, independent
    pell_eligible BOOLEAN DEFAULT 0,
    pell_amount REAL,
    verification_status TEXT DEFAULT 'not_required',
    imported_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (student_id) REFERENCES students(student_id),
    UNIQUE(student_id, academic_year)
);

-- Aid Packages
CREATE TABLE IF NOT EXISTS aid_packages (
    package_id INTEGER PRIMARY KEY AUTOINCREMENT,
    student_id INTEGER NOT NULL,
    academic_year TEXT NOT NULL,
    total_aid_amount REAL DEFAULT 0,
    total_grants REAL DEFAULT 0,
    total_scholarships REAL DEFAULT 0,
    total_loans REAL DEFAULT 0,
    total_work_study REAL DEFAULT 0,
    package_status TEXT DEFAULT 'offered',  -- offered, accepted, declined, revised
    offered_date DATE,
    response_deadline DATE,
    response_date DATE,
    created_by INTEGER,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (student_id) REFERENCES students(student_id),
    UNIQUE(student_id, academic_year)
);

-- Aid Components
CREATE TABLE IF NOT EXISTS aid_components (
    component_id INTEGER PRIMARY KEY AUTOINCREMENT,
    package_id INTEGER NOT NULL,
    aid_type TEXT NOT NULL,  -- grant, scholarship, loan, work_study
    source TEXT,  -- federal, state, institutional, private
    name TEXT NOT NULL,
    amount REAL NOT NULL,
    disbursement_plan TEXT,  -- JSON: [{term: 'Fall', amount: 1000}, ...]
    terms_conditions TEXT,
    is_need_based BOOLEAN DEFAULT 0,
    is_renewable BOOLEAN DEFAULT 0,
    status TEXT DEFAULT 'offered',
    FOREIGN KEY (package_id) REFERENCES aid_packages(package_id) ON DELETE CASCADE
);

-- Scholarships
CREATE TABLE IF NOT EXISTS scholarships (
    scholarship_id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    description TEXT,
    amount REAL NOT NULL,
    amount_type TEXT DEFAULT 'fixed',  -- fixed, variable, full_tuition
    scholarship_type TEXT DEFAULT 'merit',  -- merit, need, athletic, departmental
    eligibility_criteria TEXT,  -- JSON with requirements
    min_gpa REAL,
    required_major TEXT,
    required_class_year TEXT,
    deadline DATE,
    renewable BOOLEAN DEFAULT 0,
    max_renewals INTEGER,
    available_count INTEGER,  -- NULL for unlimited
    total_awarded INTEGER DEFAULT 0,
    donor_name TEXT,
    is_active BOOLEAN DEFAULT 1,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Scholarship Applications
CREATE TABLE IF NOT EXISTS scholarship_applications (
    app_id INTEGER PRIMARY KEY AUTOINCREMENT,
    scholarship_id INTEGER NOT NULL,
    student_id INTEGER NOT NULL,
    application_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    status TEXT DEFAULT 'pending',  -- pending, under_review, awarded, denied
    essay_text TEXT,
    recommendation_1 TEXT,
    recommendation_2 TEXT,
    transcript_url TEXT,
    resume_url TEXT,
    gpa REAL,
    reviewer_id INTEGER,
    review_date TIMESTAMP,
    review_score REAL,
    review_comments TEXT,
    FOREIGN KEY (scholarship_id) REFERENCES scholarships(scholarship_id),
    FOREIGN KEY (student_id) REFERENCES students(student_id),
    UNIQUE(scholarship_id, student_id)
);

-- Scholarship Awards
CREATE TABLE IF NOT EXISTS scholarship_awards (
    award_id INTEGER PRIMARY KEY AUTOINCREMENT,
    scholarship_id INTEGER NOT NULL,
    student_id INTEGER NOT NULL,
    academic_year TEXT NOT NULL,
    amount REAL NOT NULL,
    award_date DATE,
    status TEXT DEFAULT 'active',  -- active, suspended, revoked, completed
    is_renewable BOOLEAN DEFAULT 0,
    renewal_deadline DATE,
    renewal_status TEXT,  -- NULL, pending, approved, denied
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (scholarship_id) REFERENCES scholarships(scholarship_id),
    FOREIGN KEY (student_id) REFERENCES students(student_id)
);

-- Disbursements
CREATE TABLE IF NOT EXISTS disbursements (
    disbursement_id INTEGER PRIMARY KEY AUTOINCREMENT,
    award_id INTEGER,
    component_id INTEGER,
    student_id INTEGER NOT NULL,
    amount REAL NOT NULL,
    disbursement_type TEXT,  -- scholarship, grant, loan, work_study
    disbursement_date DATE NOT NULL,
    scheduled_date DATE,
    academic_term TEXT,  -- Fall, Spring, Summer
    status TEXT DEFAULT 'pending',  -- pending, processed, failed, cancelled
    payment_method TEXT DEFAULT 'account_credit',
    transaction_id TEXT,
    processed_by INTEGER,
    processed_at TIMESTAMP,
    error_message TEXT,
    FOREIGN KEY (award_id) REFERENCES scholarship_awards(award_id),
    FOREIGN KEY (component_id) REFERENCES aid_components(component_id),
    FOREIGN KEY (student_id) REFERENCES students(student_id)
);

-- Renewal Requirements
CREATE TABLE IF NOT EXISTS renewal_requirements (
    requirement_id INTEGER PRIMARY KEY AUTOINCREMENT,
    award_id INTEGER NOT NULL,
    academic_year TEXT NOT NULL,
    gpa_required REAL,
    credit_hours_required INTEGER,
    enrollment_status_required TEXT,  -- full_time, half_time
    service_hours_required INTEGER,
    other_requirements TEXT,
    verification_deadline DATE,
    is_met BOOLEAN,
    verified_by INTEGER,
    verified_date TIMESTAMP,
    notes TEXT,
    FOREIGN KEY (award_id) REFERENCES scholarship_awards(award_id) ON DELETE CASCADE
);

-- Compliance Reports
CREATE TABLE IF NOT EXISTS compliance_reports (
    report_id INTEGER PRIMARY KEY AUTOINCREMENT,
    report_type TEXT NOT NULL,  -- FISAP, NSLDS, COD, institutional
    academic_year TEXT NOT NULL,
    report_period TEXT,
    generated_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    generated_by INTEGER,
    file_url TEXT,
    submitted_date TIMESTAMP,
    submission_status TEXT,  -- draft, submitted, accepted, rejected
    notes TEXT
);

-- External Scholarships
CREATE TABLE IF NOT EXISTS external_scholarships (
    external_id INTEGER PRIMARY KEY AUTOINCREMENT,
    student_id INTEGER NOT NULL,
    provider_name TEXT NOT NULL,
    scholarship_name TEXT,
    amount REAL NOT NULL,
    academic_year TEXT NOT NULL,
    disbursement_date DATE,
    is_recurring BOOLEAN DEFAULT 0,
    contact_email TEXT,
    contact_phone TEXT,
    documentation_url TEXT,
    reported_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (student_id) REFERENCES students(student_id)
);

-- Payment Schedules
CREATE TABLE IF NOT EXISTS payment_schedules (
    schedule_id INTEGER PRIMARY KEY AUTOINCREMENT,
    award_id INTEGER,
    component_id INTEGER,
    student_id INTEGER NOT NULL,
    total_amount REAL NOT NULL,
    payment_date DATE NOT NULL,
    amount REAL NOT NULL,
    academic_term TEXT,
    status TEXT DEFAULT 'scheduled',  -- scheduled, paid, cancelled
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (award_id) REFERENCES scholarship_awards(award_id),
    FOREIGN KEY (component_id) REFERENCES aid_components(component_id),
    FOREIGN KEY (student_id) REFERENCES students(student_id)
);

-- Create indexes
CREATE INDEX IF NOT EXISTS idx_fin_aid_apps_student ON financial_aid_applications(student_id);
CREATE INDEX IF NOT EXISTS idx_fin_aid_apps_year ON financial_aid_applications(academic_year);
CREATE INDEX IF NOT EXISTS idx_fafsa_student ON fafsa_data(student_id);
CREATE INDEX IF NOT EXISTS idx_aid_packages_student ON aid_packages(student_id);
CREATE INDEX IF NOT EXISTS idx_aid_components_package ON aid_components(package_id);
CREATE INDEX IF NOT EXISTS idx_scholarships_active ON scholarships(is_active);
CREATE INDEX IF NOT EXISTS idx_scholarship_apps_student ON scholarship_applications(student_id);
CREATE INDEX IF NOT EXISTS idx_scholarship_awards_student ON scholarship_awards(student_id);
CREATE INDEX IF NOT EXISTS idx_disbursements_student ON disbursements(student_id);
CREATE INDEX IF NOT EXISTS idx_disbursements_date ON disbursements(disbursement_date);
"""

def create_financial_aid_tables(conn):
    """Create all financial aid tables"""
    cursor = conn.cursor()
    cursor.executescript(FINANCIAL_AID_SCHEMA)
    conn.commit()
    print("Financial Aid & Scholarship Management tables created successfully")

if __name__ == "__main__":
    from education_system.university_system.infrastructure.database.db import sqlite3
    from education_system.university_system.modules.shared.constants.paths import DEFAULT_DB_PATH

    with sqlite3.connect(DEFAULT_DB_PATH) as conn:
        create_financial_aid_tables(conn)
