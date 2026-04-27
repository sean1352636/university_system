CREATE TABLE IF NOT EXISTS syllabus_templates (
                    template_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    description TEXT,
                    sections_json TEXT NOT NULL,
                    level TEXT DEFAULT 'undergraduate',
                    created_by TEXT,
                    is_active INTEGER DEFAULT 1,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP
                );
