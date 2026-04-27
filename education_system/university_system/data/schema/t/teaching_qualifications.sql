CREATE TABLE IF NOT EXISTS teaching_qualifications (
                    qualification_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id TEXT NOT NULL,
                    subject_area TEXT NOT NULL,
                    course_code TEXT,
                    qualification_level TEXT DEFAULT 'qualified',
                    verified INTEGER DEFAULT 0,
                    verified_by TEXT,
                    verified_date TEXT,
                    notes TEXT,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP
                );
