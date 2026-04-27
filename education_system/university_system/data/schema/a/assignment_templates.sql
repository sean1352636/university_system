CREATE TABLE IF NOT EXISTS assignment_templates (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                description TEXT,
                template_data TEXT NOT NULL,
                category TEXT,
                created_by INTEGER,
                created_at TEXT NOT NULL,
                is_active INTEGER DEFAULT 1,
                usage_count INTEGER DEFAULT 0,
                FOREIGN KEY (created_by) REFERENCES users (id)
            );
