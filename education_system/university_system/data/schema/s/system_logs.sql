CREATE TABLE IF NOT EXISTS system_logs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    action_type TEXT,
                    description TEXT,
                    details TEXT,
                    created_date TEXT DEFAULT CURRENT_TIMESTAMP
                );
