CREATE TABLE IF NOT EXISTS logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                user_id TEXT,
                username TEXT,
                action TEXT,
                status TEXT,
                module TEXT,
                message TEXT,
                ip_address TEXT,
                user_agent TEXT
            , "log_id" INTEGER, "new_values" TEXT, "old_values" TEXT, "record_id" TEXT, "session_id" TEXT, "table_name" TEXT);
