CREATE TABLE IF NOT EXISTS admission_applications (
            application_id INTEGER PRIMARY KEY AUTOINCREMENT,
            prospect_id INTEGER NOT NULL,
            application_type TEXT NOT NULL,
            program_applied TEXT NOT NULL,
            academic_year TEXT NOT NULL,
            semester TEXT NOT NULL,
            submission_date TEXT DEFAULT CURRENT_TIMESTAMP,
            status TEXT DEFAULT 'submitted',
            decision TEXT,
            decision_date TEXT,
            enrollment_confirmed BOOLEAN DEFAULT 0,
            application_fee_paid BOOLEAN DEFAULT 0,
            FOREIGN KEY (prospect_id) REFERENCES admission_prospects (prospect_id)
        );
