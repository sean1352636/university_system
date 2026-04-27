CREATE TABLE IF NOT EXISTS scheduled_reports (
            report_id INTEGER PRIMARY KEY AUTOINCREMENT,
            report_name TEXT NOT NULL,
            report_type TEXT NOT NULL,
            schedule_frequency TEXT NOT NULL,
            recipients TEXT NOT NULL,
            last_run_date TEXT,
            next_run_date TEXT,
            is_active BOOLEAN DEFAULT 1,
            report_config TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        );
