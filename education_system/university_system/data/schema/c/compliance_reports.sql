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
