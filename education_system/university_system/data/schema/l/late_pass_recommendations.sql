CREATE TABLE IF NOT EXISTS late_pass_recommendations (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        student_id TEXT NOT NULL,
                        assignment_id INTEGER,
                        recommendation TEXT NOT NULL,
                        confidence_score REAL NOT NULL,
                        reasoning_json TEXT,
                        created_at TEXT NOT NULL
                    );
