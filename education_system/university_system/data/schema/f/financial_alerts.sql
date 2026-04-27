CREATE TABLE IF NOT EXISTS financial_alerts (
        alert_id INTEGER PRIMARY KEY AUTOINCREMENT,
        alert_type TEXT NOT NULL,
        priority TEXT DEFAULT 'medium',
        title TEXT NOT NULL,
        message TEXT NOT NULL,
        student_id TEXT,
        amount DECIMAL(10,2),
        currency TEXT DEFAULT 'GBP',
        status TEXT DEFAULT 'active',
        created_at TEXT DEFAULT CURRENT_TIMESTAMP,
        acknowledged_at TEXT,
        resolved_at TEXT,
        acknowledged_by TEXT,
        resolved_by TEXT,
        metadata TEXT,
        FOREIGN KEY (student_id) REFERENCES students (student_id)
    );
