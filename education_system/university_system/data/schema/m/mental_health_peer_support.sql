CREATE TABLE IF NOT EXISTS mental_health_peer_support (
            support_id INTEGER PRIMARY KEY AUTOINCREMENT,
            supporter_student_id TEXT NOT NULL,
            supported_student_id TEXT NOT NULL,
            support_type TEXT NOT NULL,
            notes TEXT,
            session_count INTEGER DEFAULT 0,
            last_session_date TEXT,
            status TEXT DEFAULT 'active',
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        , "match_date" TEXT DEFAULT CURRENT_DATE);
