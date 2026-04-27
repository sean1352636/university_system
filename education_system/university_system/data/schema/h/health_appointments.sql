CREATE TABLE IF NOT EXISTS health_appointments (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    student_id TEXT,
                    appointment_type TEXT,
                    appointment_date TEXT,
                    appointment_time TEXT,
                    provider TEXT,
                    reason TEXT,
                    status TEXT DEFAULT 'scheduled',
                    notes TEXT,
                    scheduled_at TEXT,
                    FOREIGN KEY (student_id) REFERENCES students (student_id)
                );
