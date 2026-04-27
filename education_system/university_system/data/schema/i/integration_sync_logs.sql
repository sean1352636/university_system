CREATE TABLE IF NOT EXISTS integration_sync_logs (
            log_id INTEGER PRIMARY KEY AUTOINCREMENT,
            install_id INTEGER NOT NULL,
            sync_start_time TEXT DEFAULT CURRENT_TIMESTAMP,
            sync_end_time TEXT,
            sync_status TEXT NOT NULL,
            records_synced INTEGER DEFAULT 0,
            errors_encountered INTEGER DEFAULT 0,
            error_details TEXT,
            FOREIGN KEY (install_id) REFERENCES installed_integrations (install_id)
        );
