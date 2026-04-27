CREATE TABLE IF NOT EXISTS ai_alert_settings (
                    id INTEGER PRIMARY KEY,
                    setting_name TEXT UNIQUE,
                    setting_value TEXT,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
