CREATE TABLE IF NOT EXISTS response_templates (
            template_id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            subject TEXT,
            content TEXT NOT NULL,
            category TEXT,
            created_by TEXT NOT NULL,
            created_datetime TEXT NOT NULL,
            is_active BOOLEAN DEFAULT 1,
            usage_count INTEGER DEFAULT 0,
            variables TEXT  -- JSON array of variable names
        );
