CREATE TABLE IF NOT EXISTS exit_reasons_summary (
                    summary_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    period TEXT NOT NULL,
                    department TEXT,
                    reason_category TEXT NOT NULL,
                    count INTEGER DEFAULT 0,
                    percentage REAL,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP
                );
