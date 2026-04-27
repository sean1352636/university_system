CREATE TABLE IF NOT EXISTS scheduling_system_settings (
                key TEXT PRIMARY KEY,
                value TEXT,
                description TEXT,
                last_modified TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            , "id" INTEGER, "setting_key" TEXT, "setting_value" TEXT, updated_at TIMESTAMP DEFAULT NULL);
