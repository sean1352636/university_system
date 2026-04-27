CREATE TABLE IF NOT EXISTS sso_providers (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                provider_id TEXT UNIQUE NOT NULL,
                provider_type TEXT NOT NULL CHECK(provider_type IN ('saml', 'oidc')),
                display_name TEXT NOT NULL,
                config_json TEXT NOT NULL,
                is_enabled BOOLEAN DEFAULT 1,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
