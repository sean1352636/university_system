CREATE TABLE IF NOT EXISTS data_retention_policies (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            data_type TEXT,
            retention_period_days INTEGER,
            auto_archive INTEGER DEFAULT 0,
            auto_delete INTEGER DEFAULT 0,
            created_at TEXT
        , retention_period_months INTEGER, deletion_method TEXT DEFAULT 'soft', last_cleanup_date TEXT, is_active BOOLEAN DEFAULT 1, updated_at TEXT, "policy_id" INTEGER);
