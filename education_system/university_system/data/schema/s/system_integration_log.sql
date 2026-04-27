CREATE TABLE IF NOT EXISTS system_integration_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                source_system TEXT,
                target_system TEXT,
                operation TEXT,
                status TEXT,
                details TEXT,
                timestamp TEXT
            );
