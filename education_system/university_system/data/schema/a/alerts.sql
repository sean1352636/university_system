CREATE TABLE IF NOT EXISTS alerts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                alert_type TEXT,
                message TEXT,
                severity TEXT DEFAULT 'medium',
                triggered_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                acknowledged BOOLEAN DEFAULT FALSE,
                resolved BOOLEAN DEFAULT FALSE,
                resolved_at DATETIME,
                user_id TEXT,
                metadata TEXT
            , "alert_id" INTEGER, "created_at" TEXT DEFAULT CURRENT_TIMESTAMP, "dismissed_at" TEXT, "expires_at" TEXT, "priority" TEXT DEFAULT 'medium', "read_at" TEXT, "status" TEXT DEFAULT 'active', "target_user_id" INTEGER, "target_user_type" TEXT, "title" TEXT);
