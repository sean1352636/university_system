CREATE TABLE IF NOT EXISTS counseling_appointments (
                    appointment_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    student_id TEXT NOT NULL,
                    appointment_date TEXT NOT NULL,
                    appointment_time TEXT NOT NULL,
                    counselor_name TEXT,
                    appointment_type TEXT,
                    status TEXT DEFAULT 'Scheduled',
                    notes TEXT,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (student_id) REFERENCES students(student_id)
                );
