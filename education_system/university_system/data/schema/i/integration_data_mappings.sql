CREATE TABLE IF NOT EXISTS integration_data_mappings (
            mapping_id INTEGER PRIMARY KEY AUTOINCREMENT,
            install_id INTEGER NOT NULL,
            source_field TEXT NOT NULL,
            target_field TEXT NOT NULL,
            transformation_rule TEXT,
            is_active BOOLEAN DEFAULT 1,
            FOREIGN KEY (install_id) REFERENCES installed_integrations (install_id)
        );
