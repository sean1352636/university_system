CREATE TABLE IF NOT EXISTS ai_grading_results (
            grading_id INTEGER PRIMARY KEY AUTOINCREMENT,
            submission_id INTEGER NOT NULL,
            assignment_type TEXT NOT NULL,
            auto_score REAL,
            max_score REAL,
            grading_criteria TEXT,
            feedback_generated TEXT,
            confidence_score REAL,
            requires_manual_review BOOLEAN DEFAULT 0,
            manual_override_score REAL,
            graded_at TEXT DEFAULT CURRENT_TIMESTAMP
        );
