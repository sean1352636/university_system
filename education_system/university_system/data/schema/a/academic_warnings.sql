CREATE TABLE IF NOT EXISTS academic_warnings (
                    warning_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    student_id TEXT NOT NULL,
                    warning_type TEXT NOT NULL,
                    severity TEXT NOT NULL,
                    warning_message TEXT NOT NULL,
                    trigger_metric TEXT,
                    trigger_value TEXT,
                    recommendations_json TEXT,
                    acknowledged BOOLEAN DEFAULT 0,
                    acknowledged_at TEXT,
                    resolved BOOLEAN DEFAULT 0,
                    resolved_at TEXT,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP
                );
