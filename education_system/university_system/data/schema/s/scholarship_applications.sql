CREATE TABLE IF NOT EXISTS scholarship_applications (
    application_id INTEGER PRIMARY KEY AUTOINCREMENT,
    student_id TEXT NOT NULL,
    scholarship_id INTEGER NOT NULL,
    application_date TEXT DEFAULT CURRENT_TIMESTAMP,
    status TEXT DEFAULT 'pending',
    essay TEXT,
    additional_documents TEXT,
    reviewer_id TEXT,
    review_date TEXT,
    review_notes TEXT,
    decision_date TEXT,
    award_amount DECIMAL(10,2), essay_text TEXT, gpa REAL, transcript_url TEXT, resume_url TEXT, "academic_year" TEXT, "financial_need_statement" TEXT, "reviewed_by" INTEGER,
    FOREIGN KEY (student_id) REFERENCES students (student_id),
    FOREIGN KEY (scholarship_id) REFERENCES scholarships (scholarship_id)
);
