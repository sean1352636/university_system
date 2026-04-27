CREATE TABLE IF NOT EXISTS event_templates (
                id TEXT PRIMARY KEY,
                template_name TEXT NOT NULL,
                template_data TEXT NOT NULL,
                created_by TEXT,
                created_at TEXT NOT NULL,
                is_active BOOLEAN DEFAULT TRUE
            );
