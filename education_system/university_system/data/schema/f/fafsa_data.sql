CREATE TABLE IF NOT EXISTS fafsa_data (
    fafsa_id INTEGER PRIMARY KEY AUTOINCREMENT,
    student_id INTEGER NOT NULL,
    academic_year TEXT NOT NULL,
    efc INTEGER,  -- Expected Family Contribution
    submission_date DATE,
    processed_date DATE,
    sai INTEGER,  -- Student Aid Index (new FAFSA metric)
    dependency_status TEXT,  -- dependent, independent
    pell_eligible BOOLEAN DEFAULT 0,
    pell_amount REAL,
    verification_status TEXT DEFAULT 'not_required',
    imported_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (student_id) REFERENCES students(student_id),
    UNIQUE(student_id, academic_year)
);
