CREATE TABLE IF NOT EXISTS mental_health_meditation_sessions (
            session_id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            description TEXT,
            audio_url TEXT NOT NULL,
            duration_minutes INTEGER NOT NULL,
            category TEXT NOT NULL,
            difficulty_level TEXT DEFAULT 'beginner',
            play_count INTEGER DEFAULT 0,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        );
