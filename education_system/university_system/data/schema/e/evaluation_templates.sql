CREATE TABLE IF NOT EXISTS evaluation_templates (
                template_id INTEGER PRIMARY KEY AUTOINCREMENT,
                template_name TEXT NOT NULL,
                template_type TEXT NOT NULL,
                description TEXT,
                created_by TEXT,
                created_at TEXT NOT NULL DEFAULT (datetime('now')),
                is_active INTEGER DEFAULT 1
            , "is_default" BOOLEAN DEFAULT 0);
