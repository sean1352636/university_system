CREATE TABLE IF NOT EXISTS teaching_portfolios (
                portfolio_id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT UNIQUE NOT NULL,
                teaching_philosophy TEXT,
                teaching_interests TEXT,
                courses_taught TEXT,
                teaching_innovations TEXT,
                awards_recognition TEXT,
                student_feedback_summary TEXT,
                professional_development TEXT,
                last_updated TEXT DEFAULT CURRENT_TIMESTAMP,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            );
