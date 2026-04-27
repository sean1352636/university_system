CREATE TABLE IF NOT EXISTS staff_mentoring_goals (
                    goal_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    match_id INTEGER NOT NULL,
                    title TEXT NOT NULL,
                    description TEXT,
                    target_date TEXT,
                    completion_date TEXT,
                    status TEXT DEFAULT 'in_progress',
                    progress_pct INTEGER DEFAULT 0,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (match_id) REFERENCES staff_mentoring_matches(match_id)
                );
