CREATE TABLE IF NOT EXISTS ai_detector_submissions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                student_id TEXT NOT NULL,
                submission_text TEXT NOT NULL,
                title TEXT,
                course_code TEXT,
                assignment_id TEXT,
                submission_date TEXT NOT NULL,
                word_count INTEGER,
                character_count INTEGER,
                institution_id TEXT
            );
