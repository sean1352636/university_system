CREATE TABLE IF NOT EXISTS configuration_audit (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            config_key TEXT NOT NULL,
            old_value TEXT,
            new_value TEXT,
            description TEXT,
            changed_by INTEGER,
            changed_at TEXT,
            FOREIGN KEY (changed_by) REFERENCES users (id)
        );
