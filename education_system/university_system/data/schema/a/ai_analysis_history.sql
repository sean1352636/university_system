CREATE TABLE IF NOT EXISTS ai_analysis_history (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        submission_id INTEGER,
        student_id TEXT,
        student_name TEXT,
        ai_probability REAL,
        analysis_date TEXT,
        course_name TEXT,
        text_content TEXT,
        fingerprint_data TEXT,
        FOREIGN KEY (submission_id) REFERENCES ai_detector_submissions (id)
    );
