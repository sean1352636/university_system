CREATE TABLE IF NOT EXISTS mental_health_appointments (
            appointment_id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id TEXT NOT NULL,
            counselor_id INTEGER,
            appointment_type TEXT NOT NULL,
            appointment_date TEXT NOT NULL,
            appointment_time TEXT NOT NULL,
            duration_minutes INTEGER DEFAULT 50,
            is_anonymous INTEGER DEFAULT 0,
            anonymous_code TEXT,
            mode TEXT DEFAULT 'in-person',
            location TEXT,
            notes TEXT,
            status TEXT DEFAULT 'scheduled',
            created_at TEXT DEFAULT CURRENT_TIMESTAMP, "updated_at" TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (counselor_id) REFERENCES mental_health_counselors (counselor_id)
        );
