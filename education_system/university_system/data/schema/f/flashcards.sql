CREATE TABLE IF NOT EXISTS flashcards (
                    flashcard_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    student_id TEXT NOT NULL,
                    course_id TEXT,
                    deck_name TEXT NOT NULL,
                    question TEXT NOT NULL,
                    answer TEXT NOT NULL,
                    difficulty_rating INTEGER DEFAULT 0,
                    last_reviewed TEXT,
                    next_review TEXT,
                    review_count INTEGER DEFAULT 0,
                    correct_count INTEGER DEFAULT 0,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP
                );
