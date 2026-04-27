CREATE TABLE IF NOT EXISTS academic_misconduct_evidence (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            case_id TEXT NOT NULL,
            file_name TEXT NOT NULL,
            file_path TEXT,
            file_size TEXT,
            uploaded_date TEXT NOT NULL,
            uploaded_by TEXT, file_hash TEXT DEFAULT '', category TEXT DEFAULT 'Document', notes TEXT DEFAULT '',
            FOREIGN KEY (case_id) REFERENCES academic_misconduct_cases(case_id)
        );
