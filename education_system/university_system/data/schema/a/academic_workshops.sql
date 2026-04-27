CREATE TABLE IF NOT EXISTS academic_workshops (
                workshop_id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                description TEXT,
                instructor TEXT,
                date TEXT,
                time TEXT,
                location TEXT,
                max_participants INTEGER DEFAULT 30,
                registered INTEGER DEFAULT 0,
                status TEXT DEFAULT 'upcoming',
                created_at TEXT
            );
