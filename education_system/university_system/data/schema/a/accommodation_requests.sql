CREATE TABLE IF NOT EXISTS accommodation_requests (
    request_id INTEGER PRIMARY KEY AUTOINCREMENT,
    student_id INTEGER NOT NULL,
    accommodation_type TEXT NOT NULL,  -- extended_time, alternative_format, etc.
    description TEXT,
    status TEXT DEFAULT 'pending',  -- pending, approved, denied
    requested_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    reviewed_by INTEGER,
    review_date TIMESTAMP,
    review_notes TEXT, student_name TEXT, student_email TEXT, submitted_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP, reviewer_notes TEXT, "reviewed_date" TIMESTAMP, "reviewer_id" TEXT,
    FOREIGN KEY (student_id) REFERENCES students(student_id)
);
