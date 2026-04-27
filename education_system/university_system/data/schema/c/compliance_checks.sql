CREATE TABLE IF NOT EXISTS compliance_checks (
            check_id INTEGER PRIMARY KEY AUTOINCREMENT,
            check_type TEXT NOT NULL,
            check_date DATE,
            status TEXT,
            details TEXT,
            resolved BOOLEAN DEFAULT FALSE
        );
