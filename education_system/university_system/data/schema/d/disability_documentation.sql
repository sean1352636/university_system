CREATE TABLE IF NOT EXISTS disability_documentation (
    doc_id INTEGER PRIMARY KEY AUTOINCREMENT,
    student_id INTEGER NOT NULL,
    disability_type TEXT NOT NULL,
    file_url TEXT,
    uploaded_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    expiry_date DATE,
    verified_by INTEGER,
    verified_date TIMESTAMP,
    FOREIGN KEY (student_id) REFERENCES students(student_id)
);
