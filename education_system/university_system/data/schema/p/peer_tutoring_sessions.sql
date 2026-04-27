CREATE TABLE IF NOT EXISTS peer_tutoring_sessions (
                session_id INTEGER PRIMARY KEY AUTOINCREMENT,
                tutor_id TEXT NOT NULL,
                subject TEXT,
                description TEXT,
                availability TEXT,
                rate TEXT DEFAULT 'Free',
                status TEXT DEFAULT 'available',
                created_at TEXT
            );
