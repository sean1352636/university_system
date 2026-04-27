CREATE TABLE IF NOT EXISTS medical_conditions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    student_id TEXT,
                    condition_name TEXT,
                    icd_code TEXT,
                    severity TEXT,
                    diagnosed_date TEXT,
                    status TEXT DEFAULT 'active',
                    provider TEXT,
                    notes TEXT,
                    created_at TEXT,
                    FOREIGN KEY (student_id) REFERENCES students (student_id)
                );
