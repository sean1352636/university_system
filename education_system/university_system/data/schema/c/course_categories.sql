CREATE TABLE IF NOT EXISTS course_categories (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE NOT NULL,
            description TEXT,
            color_code TEXT,
            created_at TEXT NOT NULL
        );
