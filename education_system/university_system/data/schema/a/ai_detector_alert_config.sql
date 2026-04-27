CREATE TABLE IF NOT EXISTS ai_detector_alert_config (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    config_key TEXT UNIQUE NOT NULL,
                    config_value TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    updated_by TEXT
                );
