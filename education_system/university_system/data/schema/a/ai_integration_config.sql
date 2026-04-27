CREATE TABLE IF NOT EXISTS ai_integration_config (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    service_name TEXT UNIQUE,
                    api_key TEXT,
                    enabled INTEGER DEFAULT 1,
                    last_sync TIMESTAMP,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
