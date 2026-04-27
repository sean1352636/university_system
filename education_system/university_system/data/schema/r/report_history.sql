CREATE TABLE IF NOT EXISTS report_history (
                        history_id INTEGER PRIMARY KEY AUTOINCREMENT,
                        report_id INTEGER,
                        report_type TEXT NOT NULL,
                        generated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        generated_by TEXT,
                        file_path TEXT,
                        file_size INTEGER,
                        recipients_json TEXT,
                        status TEXT DEFAULT 'success',
                        error_message TEXT,
                        FOREIGN KEY (report_id) REFERENCES scheduled_reports(report_id)
                    );
