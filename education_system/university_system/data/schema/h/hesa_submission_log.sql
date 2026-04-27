CREATE TABLE IF NOT EXISTS hesa_submission_log (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    return_id INTEGER NOT NULL,
                    action TEXT NOT NULL,
                    details TEXT,
                    performed_by TEXT,
                    performed_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (return_id) REFERENCES hesa_returns(id)
                );
