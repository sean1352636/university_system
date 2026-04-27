CREATE TABLE IF NOT EXISTS risk_assessments (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    student_id TEXT,
                    assessment_type TEXT,
                    risk_score INTEGER,
                    risk_factors TEXT,
                    recommendations TEXT,
                    assessed_date TEXT,
                    assessed_by TEXT,
                    follow_up_date TEXT,
                    created_at TEXT,
                    FOREIGN KEY (student_id) REFERENCES students (student_id)
                );
