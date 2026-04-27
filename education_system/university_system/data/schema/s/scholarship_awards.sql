CREATE TABLE IF NOT EXISTS scholarship_awards (
    award_id INTEGER PRIMARY KEY AUTOINCREMENT,
    scholarship_id INTEGER NOT NULL,
    student_id INTEGER NOT NULL,
    academic_year TEXT NOT NULL,
    amount REAL NOT NULL,
    award_date DATE,
    status TEXT DEFAULT 'active',  -- active, suspended, revoked, completed
    is_renewable BOOLEAN DEFAULT 0,
    renewal_deadline DATE,
    renewal_status TEXT,  -- NULL, pending, approved, denied
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP, "amount_awarded" REAL, "application_id" INTEGER, "disbursement_schedule" TEXT, "terms_accepted" BOOLEAN DEFAULT 0, "terms_accepted_date" TIMESTAMP,
    FOREIGN KEY (scholarship_id) REFERENCES scholarships(scholarship_id),
    FOREIGN KEY (student_id) REFERENCES students(student_id)
);
