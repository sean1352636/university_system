CREATE TABLE IF NOT EXISTS qa_board (
                    question_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    course_id TEXT NOT NULL,
                    student_id TEXT NOT NULL,
                    anonymous_id TEXT NOT NULL,
                    question_title TEXT NOT NULL,
                    question_text TEXT NOT NULL,
                    category TEXT DEFAULT 'General',
                    difficulty_level TEXT DEFAULT 'Medium',
                    upvotes INTEGER DEFAULT 0,
                    downvotes INTEGER DEFAULT 0,
                    view_count INTEGER DEFAULT 0,
                    is_answered BOOLEAN DEFAULT 0,
                    is_resolved BOOLEAN DEFAULT 0,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
                );
