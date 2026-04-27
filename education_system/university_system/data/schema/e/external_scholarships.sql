CREATE TABLE IF NOT EXISTS external_scholarships (
    external_id INTEGER PRIMARY KEY AUTOINCREMENT,
    student_id INTEGER NOT NULL,
    provider_name TEXT NOT NULL,
    scholarship_name TEXT,
    amount REAL NOT NULL,
    academic_year TEXT NOT NULL,
    disbursement_date DATE,
    is_recurring BOOLEAN DEFAULT 0,
    contact_email TEXT,
    contact_phone TEXT,
    documentation_url TEXT,
    reported_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (student_id) REFERENCES students(student_id)
);
