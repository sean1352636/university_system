CREATE TABLE IF NOT EXISTS ai_detector_activity_log (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id TEXT NOT NULL,
                    action TEXT NOT NULL,
                    action_type TEXT,
                    target_id TEXT,
                    details TEXT,
                    ip_address TEXT,
                    timestamp TEXT NOT NULL
                );
