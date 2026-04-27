CREATE TABLE IF NOT EXISTS installed_integrations (
            install_id INTEGER PRIMARY KEY AUTOINCREMENT,
            integration_id INTEGER NOT NULL,
            installed_by TEXT NOT NULL,
            installation_date TEXT DEFAULT CURRENT_TIMESTAMP,
            version_installed TEXT,
            configuration TEXT,
            status TEXT DEFAULT 'active',
            last_sync_date TEXT,
            sync_frequency TEXT,
            is_enabled BOOLEAN DEFAULT 1,
            FOREIGN KEY (integration_id) REFERENCES integration_catalog (integration_id)
        );
