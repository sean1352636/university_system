CREATE TABLE IF NOT EXISTS submission_annotations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            submission_id INTEGER NOT NULL,
            reviewer_id INTEGER NOT NULL,
            line_number INTEGER,
            position_start INTEGER,
            position_end INTEGER,
            comment TEXT NOT NULL,
            category TEXT DEFAULT 'suggestion' CHECK (category IN ('praise', 'suggestion', 'correction', 'question')),
            student_response TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (submission_id) REFERENCES assignment_submissions (id),
            FOREIGN KEY (reviewer_id) REFERENCES users (id)
        );
