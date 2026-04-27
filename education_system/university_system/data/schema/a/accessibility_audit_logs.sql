CREATE TABLE IF NOT EXISTS accessibility_audit_logs (
    log_id INTEGER PRIMARY KEY AUTOINCREMENT,
    page_url TEXT NOT NULL,
    issues_found TEXT,  -- JSON array
    severity TEXT,  -- low, medium, high, critical
    audited_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    audited_by INTEGER
);
