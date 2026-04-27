CREATE TABLE IF NOT EXISTS marketplace_reports (
                    report_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    listing_type TEXT NOT NULL,
                    listing_id INTEGER NOT NULL,
                    reporter_id TEXT NOT NULL,
                    reason TEXT NOT NULL,
                    description TEXT,
                    status TEXT DEFAULT 'Pending',
                    reviewed_at TEXT,
                    reviewed_by TEXT,
                    resolution TEXT,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (reporter_id) REFERENCES students(student_id)
                );
