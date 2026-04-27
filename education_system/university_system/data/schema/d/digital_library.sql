CREATE TABLE IF NOT EXISTS digital_library (
            digital_id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            author TEXT NOT NULL,
            file_path TEXT NOT NULL,
            file_type TEXT NOT NULL,
            file_size INTEGER,
            category TEXT,
            description TEXT,
            access_level TEXT DEFAULT 'public',
            download_count INTEGER DEFAULT 0,
            added_date TEXT NOT NULL
        );
