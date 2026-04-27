CREATE TABLE IF NOT EXISTS ai_plagiarism_checks (
            check_id INTEGER PRIMARY KEY AUTOINCREMENT,
            submission_id INTEGER NOT NULL,
            student_id TEXT NOT NULL,
            document_text TEXT NOT NULL,
            similarity_score REAL,
            matched_sources TEXT,
            flagged BOOLEAN DEFAULT 0,
            review_status TEXT DEFAULT 'pending',
            checked_at TEXT DEFAULT CURRENT_TIMESTAMP
        );
