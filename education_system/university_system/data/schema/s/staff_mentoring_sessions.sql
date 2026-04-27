CREATE TABLE IF NOT EXISTS staff_mentoring_sessions (
                    session_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    match_id INTEGER NOT NULL,
                    session_date TEXT NOT NULL,
                    duration_minutes INTEGER DEFAULT 60,
                    session_type TEXT DEFAULT 'one_on_one',
                    location TEXT,
                    virtual_link TEXT,
                    topics_discussed TEXT,
                    action_items TEXT,
                    mentor_notes TEXT,
                    mentee_notes TEXT,
                    status TEXT DEFAULT 'scheduled',
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (match_id) REFERENCES staff_mentoring_matches(match_id)
                );
