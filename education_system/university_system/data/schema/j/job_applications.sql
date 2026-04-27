CREATE TABLE IF NOT EXISTS job_applications (
            application_id INTEGER PRIMARY KEY AUTOINCREMENT,
            job_id INTEGER,
            applicant_id TEXT,
            application_date TEXT,
            status TEXT DEFAULT 'submitted',
            cover_letter TEXT,
            resume_path TEXT, "applied_date" TEXT DEFAULT CURRENT_TIMESTAMP, "notes" TEXT, "resume_id" INTEGER, "reviewed_date" TEXT, "student_id" TEXT,
            FOREIGN KEY (job_id) REFERENCES job_postings (job_id),
            FOREIGN KEY (applicant_id) REFERENCES alumni (alumni_id)
        );
