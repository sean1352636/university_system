CREATE TABLE IF NOT EXISTS advising_appointments (
                appointment_id INTEGER PRIMARY KEY AUTOINCREMENT,
                student_id TEXT NOT NULL,
                advisor_id TEXT NOT NULL,
                appointment_date TEXT NOT NULL,
                appointment_time TEXT NOT NULL,
                duration_minutes INTEGER DEFAULT 30,
                appointment_type TEXT NOT NULL,
                topic TEXT,
                notes TEXT,
                status TEXT DEFAULT 'scheduled',
                created_at TEXT NOT NULL DEFAULT (datetime('now'))
            );
