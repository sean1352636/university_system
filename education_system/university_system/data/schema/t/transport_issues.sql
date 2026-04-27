CREATE TABLE IF NOT EXISTS transport_issues (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                student_id TEXT NOT NULL,
                issue_type TEXT,
                issue_date TEXT,
                issue_time TEXT,
                description TEXT,
                report_timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                status TEXT DEFAULT 'Open'
            );
