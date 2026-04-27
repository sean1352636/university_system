CREATE TABLE IF NOT EXISTS ticket_templates (
            template_id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            title_template TEXT NOT NULL,
            description_template TEXT NOT NULL,
            category TEXT NOT NULL,
            priority TEXT NOT NULL,
            created_by TEXT NOT NULL,
            created_datetime TEXT NOT NULL,
            is_active BOOLEAN DEFAULT 1,
            usage_count INTEGER DEFAULT 0
        );
