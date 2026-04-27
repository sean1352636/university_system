CREATE TABLE IF NOT EXISTS schedule_templates (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                template_name TEXT UNIQUE,
                description TEXT,
                template_data TEXT,
                created_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                created_by TEXT
            );
