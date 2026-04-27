CREATE TABLE IF NOT EXISTS backup_log (
                    log_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    event_type TEXT,
                    filename TEXT,
                    file_size_mb REAL,
                    event_time DATETIME DEFAULT CURRENT_TIMESTAMP
                );
