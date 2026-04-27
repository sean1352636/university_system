CREATE TABLE IF NOT EXISTS audit_trail (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT NOT NULL,
                    action TEXT NOT NULL,
                    resource_type TEXT NOT NULL,
                    resource_id TEXT,
                    user_id INTEGER,
                    username TEXT,
                    ip_address TEXT,
                    details TEXT,
                    function_name TEXT,
                    module_name TEXT,
                    success INTEGER DEFAULT 1,
                    error_message TEXT,
                    data_hash TEXT
                , old_values TEXT, new_values TEXT, user_agent TEXT, duration REAL, "audit_id" INTEGER);
