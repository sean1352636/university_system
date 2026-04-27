CREATE TABLE IF NOT EXISTS ai_detector_model_rollbacks (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    from_version TEXT,
                    to_version TEXT NOT NULL,
                    reason TEXT,
                    rolled_back_by TEXT,
                    rolled_back_at TEXT NOT NULL
                );
