CREATE TABLE IF NOT EXISTS sabbatical_progress_reports (
                    report_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    application_id INTEGER NOT NULL,
                    report_type TEXT DEFAULT 'interim',
                    report_date TEXT NOT NULL,
                    content TEXT NOT NULL,
                    achievements TEXT,
                    challenges TEXT,
                    status TEXT DEFAULT 'submitted',
                    reviewer_id TEXT,
                    review_comments TEXT,
                    review_date TEXT,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (application_id) REFERENCES sabbatical_applications(application_id)
                );
