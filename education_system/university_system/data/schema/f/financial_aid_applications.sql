CREATE TABLE IF NOT EXISTS financial_aid_applications (
    application_id INTEGER PRIMARY KEY AUTOINCREMENT,
    student_id INTEGER NOT NULL,
    academic_year TEXT NOT NULL,
    application_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    status TEXT DEFAULT 'pending',  -- pending, under_review, approved, denied
    family_income REAL,
    household_size INTEGER,
    special_circumstances TEXT,
    submitted_by INTEGER,
    reviewed_by INTEGER,
    review_date TIMESTAMP,
    review_notes TEXT,
    FOREIGN KEY (student_id) REFERENCES students(student_id)
);
