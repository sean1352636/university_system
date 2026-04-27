CREATE TABLE IF NOT EXISTS print_jobs (
                    job_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    student_id TEXT NOT NULL,
                    file_name TEXT NOT NULL,
                    pages INTEGER DEFAULT 1,
                    copies INTEGER DEFAULT 1,
                    color INTEGER DEFAULT 0,
                    double_sided INTEGER DEFAULT 1,
                    paper_size TEXT DEFAULT 'A4',
                    printer_location TEXT DEFAULT '',
                    status TEXT DEFAULT 'queued',
                    cost_credits INTEGER DEFAULT 0,
                    submitted_at TEXT DEFAULT (datetime('now')),
                    completed_at TEXT
                );
