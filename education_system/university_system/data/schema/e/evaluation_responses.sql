CREATE TABLE IF NOT EXISTS evaluation_responses (
                response_id INTEGER PRIMARY KEY AUTOINCREMENT,
                evaluation_id INTEGER NOT NULL,
                student_id TEXT,
                is_complete INTEGER DEFAULT 0,
                is_anonymous INTEGER DEFAULT 1,
                time_taken_minutes INTEGER,
                submitted_at TEXT DEFAULT (datetime('now')), "response_date" TIMESTAMP DEFAULT NULL,
                FOREIGN KEY (evaluation_id) REFERENCES course_evaluations(evaluation_id) ON DELETE CASCADE
            );
