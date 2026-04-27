CREATE TABLE IF NOT EXISTS concept_explanations (
                    explanation_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    student_id TEXT NOT NULL,
                    course_id TEXT,
                    concept_name TEXT NOT NULL,
                    explanation TEXT NOT NULL,
                    difficulty_level TEXT DEFAULT 'Beginner',
                    helpful_rating INTEGER DEFAULT 0,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP
                );
