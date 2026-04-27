CREATE TABLE IF NOT EXISTS backup_history (
                    id TEXT PRIMARY KEY,
                    backup_type TEXT NOT NULL,
                    file_path TEXT NOT NULL,
                    file_size INTEGER,
                    backup_time TEXT NOT NULL,
                    status TEXT NOT NULL,
                    notes TEXT
                );
