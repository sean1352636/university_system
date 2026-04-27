CREATE TABLE IF NOT EXISTS counselling_sessions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                student_id TEXT NOT NULL,
                counsellor TEXT,
                session_date TEXT,
                notes TEXT,
                outcome TEXT,
                created_at TEXT DEFAULT (datetime('now'))
            );
