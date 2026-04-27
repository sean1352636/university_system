CREATE TABLE IF NOT EXISTS volunteer_signups (
            signup_id INTEGER PRIMARY KEY AUTOINCREMENT,
            opportunity_id INTEGER,
            student_id TEXT,
            signup_date TEXT,
            hours_completed REAL DEFAULT 0.0,
            completion_date TEXT,
            feedback TEXT,
            status TEXT DEFAULT 'signed_up',
            FOREIGN KEY (opportunity_id) REFERENCES volunteer_opportunities (opportunity_id),
            FOREIGN KEY (student_id) REFERENCES students (student_id)
        );
