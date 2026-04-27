CREATE TABLE IF NOT EXISTS integration_credentials (
            credential_id INTEGER PRIMARY KEY AUTOINCREMENT,
            install_id INTEGER NOT NULL,
            credential_type TEXT NOT NULL,
            api_key TEXT,
            api_secret TEXT,
            oauth_token TEXT,
            refresh_token TEXT,
            token_expiry TEXT,
            endpoint_url TEXT,
            additional_config TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT,
            FOREIGN KEY (install_id) REFERENCES installed_integrations (install_id)
        );
