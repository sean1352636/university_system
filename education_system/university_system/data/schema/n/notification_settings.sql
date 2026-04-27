CREATE TABLE IF NOT EXISTS notification_settings (
                        setting_key TEXT PRIMARY KEY,
                        setting_value TEXT,
                        updated_at TEXT DEFAULT CURRENT_TIMESTAMP
                    );
