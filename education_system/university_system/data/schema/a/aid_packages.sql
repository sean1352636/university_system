CREATE TABLE IF NOT EXISTS aid_packages (
    package_id INTEGER PRIMARY KEY AUTOINCREMENT,
    student_id INTEGER NOT NULL,
    academic_year TEXT NOT NULL,
    total_aid_amount REAL DEFAULT 0,
    total_grants REAL DEFAULT 0,
    total_scholarships REAL DEFAULT 0,
    total_loans REAL DEFAULT 0,
    total_work_study REAL DEFAULT 0,
    package_status TEXT DEFAULT 'offered',  -- offered, accepted, declined, revised
    offered_date DATE,
    response_deadline DATE,
    response_date DATE,
    created_by INTEGER,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (student_id) REFERENCES students(student_id),
    UNIQUE(student_id, academic_year)
);
