CREATE TABLE IF NOT EXISTS instructor_performance_history (
            performance_id INTEGER PRIMARY KEY AUTOINCREMENT,
            instructor_id TEXT NOT NULL,
            academic_year TEXT NOT NULL,
            semester TEXT NOT NULL,
            avg_overall_rating REAL,
            avg_teaching_effectiveness REAL,
            avg_course_organization REAL,
            avg_student_engagement REAL,
            total_evaluations INTEGER,
            total_responses INTEGER,
            calculated_at TEXT DEFAULT CURRENT_TIMESTAMP
        );
