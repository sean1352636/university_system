CREATE TABLE IF NOT EXISTS security_policies (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                policy_key TEXT UNIQUE NOT NULL,
                value TEXT,
                description TEXT,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP
            , policy_name TEXT, status TEXT, last_updated TEXT, "policy_type" TEXT, "policy_config" TEXT, "is_active" INTEGER DEFAULT 1, "created_at" TIMESTAMP DEFAULT CURRENT_TIMESTAMP);
