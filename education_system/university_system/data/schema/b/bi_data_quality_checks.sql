CREATE TABLE IF NOT EXISTS bi_data_quality_checks (
            check_id INTEGER PRIMARY KEY AUTOINCREMENT,
            check_name TEXT NOT NULL,
            data_source TEXT NOT NULL,
            check_type TEXT NOT NULL,
            check_rule TEXT NOT NULL,
            last_run_date TEXT,
            passed BOOLEAN,
            issues_found INTEGER,
            details TEXT,
            is_active BOOLEAN DEFAULT 1
        );
