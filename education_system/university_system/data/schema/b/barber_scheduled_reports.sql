CREATE TABLE IF NOT EXISTS barber_scheduled_reports (
                report_id INTEGER PRIMARY KEY AUTOINCREMENT,
                report_type TEXT NOT NULL,
                frequency TEXT NOT NULL,
                recipients TEXT NOT NULL,
                params TEXT,
                last_run TEXT,
                next_run TEXT,
                is_active INTEGER DEFAULT 1,
                created_by TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
