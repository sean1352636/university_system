CREATE TABLE IF NOT EXISTS lms_resources (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            description TEXT,
            file_path TEXT,
            resource_type TEXT NOT NULL DEFAULT 'document',
            course_id INTEGER,
            uploaded_by TEXT,
            download_count INTEGER NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL DEFAULT (datetime('now'))
        );
