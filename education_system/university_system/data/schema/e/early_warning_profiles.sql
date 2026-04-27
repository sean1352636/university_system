CREATE TABLE IF NOT EXISTS early_warning_profiles (
            profile_id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id TEXT NOT NULL UNIQUE,
            overall_risk_score INTEGER DEFAULT 0,
            risk_level TEXT DEFAULT 'low',
            academic_risk_score INTEGER DEFAULT 0,
            attendance_risk_score INTEGER DEFAULT 0,
            engagement_risk_score INTEGER DEFAULT 0,
            financial_risk_score INTEGER DEFAULT 0,
            last_assessed TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (student_id) REFERENCES students (student_id)
        );
