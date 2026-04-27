CREATE TABLE IF NOT EXISTS backups (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                backup_name TEXT,
                backup_path TEXT,
                backup_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                backup_size INTEGER,
                description TEXT
            );
