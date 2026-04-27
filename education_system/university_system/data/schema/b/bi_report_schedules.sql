CREATE TABLE IF NOT EXISTS bi_report_schedules (
            schedule_id INTEGER PRIMARY KEY AUTOINCREMENT,
            report_id INTEGER NOT NULL,
            schedule_name TEXT NOT NULL,
            frequency TEXT NOT NULL,
            delivery_method TEXT NOT NULL,
            recipients TEXT NOT NULL,
            export_format TEXT NOT NULL,
            last_run_date TEXT,
            next_run_date TEXT,
            is_active BOOLEAN DEFAULT 1,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (report_id) REFERENCES bi_report_definitions (report_id)
        );
