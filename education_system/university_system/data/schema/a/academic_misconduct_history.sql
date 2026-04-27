CREATE TABLE IF NOT EXISTS academic_misconduct_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            case_id TEXT NOT NULL,
            event_date TEXT NOT NULL,
            event_description TEXT NOT NULL,
            event_type TEXT DEFAULT 'info',
            created_by TEXT,
            FOREIGN KEY (case_id) REFERENCES academic_misconduct_cases(case_id)
        );
