CREATE TABLE IF NOT EXISTS prescriptions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    student_id TEXT,
                    medication_name TEXT,
                    dosage TEXT,
                    frequency TEXT,
                    prescribed_date TEXT,
                    start_date TEXT,
                    end_date TEXT,
                    prescriber TEXT,
                    pharmacy TEXT,
                    status TEXT DEFAULT 'active',
                    notes TEXT,
                    created_at TEXT,
                    FOREIGN KEY (student_id) REFERENCES students (student_id)
                );
