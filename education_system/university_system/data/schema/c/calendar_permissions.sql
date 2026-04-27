CREATE TABLE IF NOT EXISTS calendar_permissions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT NOT NULL,
                permission_type TEXT NOT NULL,
                resource_id TEXT,
                granted_by TEXT,
                granted_at TEXT NOT NULL,
                expires_at TEXT
            );
