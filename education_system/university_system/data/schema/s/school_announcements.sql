CREATE TABLE IF NOT EXISTS school_announcements (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT,
                content TEXT,
                priority TEXT DEFAULT 'normal',
                category TEXT,
                audience TEXT,
                created_by INTEGER,
                created_date TEXT,
                expiry_date TEXT,
                requires_acknowledgment BOOLEAN DEFAULT 0,
                FOREIGN KEY (created_by) REFERENCES users (id)
            );
