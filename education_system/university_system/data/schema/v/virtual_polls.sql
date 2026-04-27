CREATE TABLE IF NOT EXISTS virtual_polls (
    poll_id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id INTEGER NOT NULL,
    question TEXT NOT NULL,
    poll_type TEXT DEFAULT 'multiple_choice',  -- multiple_choice, true_false, rating, open_ended
    options TEXT,  -- JSON array for multiple choice
    correct_answer TEXT,  -- for quiz polls
    is_anonymous BOOLEAN DEFAULT 1,
    is_active BOOLEAN DEFAULT 1,
    time_limit INTEGER,  -- seconds, NULL for unlimited
    created_by INTEGER NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    closed_at TIMESTAMP, "closes_at" TIMESTAMP,
    FOREIGN KEY (session_id) REFERENCES virtual_sessions(session_id) ON DELETE CASCADE
);
