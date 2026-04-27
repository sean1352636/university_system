CREATE TABLE IF NOT EXISTS assistive_tech_requests (
    request_id INTEGER PRIMARY KEY AUTOINCREMENT,
    student_id INTEGER NOT NULL,
    technology_type TEXT NOT NULL,  -- screen_reader, magnifier, etc.
    status TEXT DEFAULT 'pending',
    requested_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    fulfilled_date TIMESTAMP,
    FOREIGN KEY (student_id) REFERENCES students(student_id)
);
