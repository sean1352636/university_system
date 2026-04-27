CREATE TABLE IF NOT EXISTS staff_mentoring_matches (
                    match_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    programme_id INTEGER NOT NULL,
                    mentor_id INTEGER NOT NULL,
                    mentee_user_id TEXT NOT NULL,
                    match_reason TEXT,
                    status TEXT DEFAULT 'proposed',
                    start_date TEXT,
                    expected_end_date TEXT,
                    actual_end_date TEXT,
                    mentor_rating INTEGER,
                    mentee_rating INTEGER,
                    notes TEXT,
                    matched_by TEXT,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (programme_id) REFERENCES staff_mentoring_programmes(programme_id),
                    FOREIGN KEY (mentor_id) REFERENCES staff_mentors(mentor_id)
                );
