CREATE TABLE IF NOT EXISTS renewal_requirements (
    requirement_id INTEGER PRIMARY KEY AUTOINCREMENT,
    award_id INTEGER NOT NULL,
    academic_year TEXT NOT NULL,
    gpa_required REAL,
    credit_hours_required INTEGER,
    enrollment_status_required TEXT,  -- full_time, half_time
    service_hours_required INTEGER,
    other_requirements TEXT,
    verification_deadline DATE,
    is_met BOOLEAN,
    verified_by INTEGER,
    verified_date TIMESTAMP,
    notes TEXT, "description" TEXT, "min_credits" INTEGER, "min_gpa" REAL, "requirement_type" TEXT, "scholarship_id" INTEGER,
    FOREIGN KEY (award_id) REFERENCES scholarship_awards(award_id) ON DELETE CASCADE
);
