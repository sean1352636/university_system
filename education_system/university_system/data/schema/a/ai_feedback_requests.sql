CREATE TABLE IF NOT EXISTS ai_feedback_requests (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        student_id TEXT NOT NULL,
                        assignment_id INTEGER,
                        draft_text TEXT NOT NULL,
                        feedback_json TEXT,
                        requested_at TEXT NOT NULL,
                        completed_at TEXT
                    );
