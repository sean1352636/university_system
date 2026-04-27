CREATE TABLE IF NOT EXISTS api_integrations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            integration_name TEXT UNIQUE,
            api_key TEXT,
            endpoint_url TEXT,
            status TEXT DEFAULT 'active',
            last_sync TEXT,
            sync_frequency TEXT DEFAULT 'daily',
            config_data TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        );
