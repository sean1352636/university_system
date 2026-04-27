CREATE TABLE IF NOT EXISTS integration_catalog (
            integration_id INTEGER PRIMARY KEY AUTOINCREMENT,
            integration_name TEXT NOT NULL,
            provider_name TEXT NOT NULL,
            integration_type TEXT NOT NULL,
            category TEXT NOT NULL,
            description TEXT,
            version TEXT,
            logo_url TEXT,
            documentation_url TEXT,
            pricing_model TEXT,
            is_official BOOLEAN DEFAULT 0,
            is_active BOOLEAN DEFAULT 1,
            rating REAL DEFAULT 0,
            install_count INTEGER DEFAULT 0,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        );
