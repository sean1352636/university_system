CREATE TABLE IF NOT EXISTS lms_lessons (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            module_id INTEGER NOT NULL,
            title TEXT NOT NULL,
            content_type TEXT NOT NULL DEFAULT 'text',
            content TEXT,
            order_index INTEGER NOT NULL DEFAULT 0,
            duration_mins INTEGER,
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            FOREIGN KEY (module_id) REFERENCES lms_modules(id)
        );
