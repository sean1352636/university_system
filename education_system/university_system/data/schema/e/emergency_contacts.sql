CREATE TABLE IF NOT EXISTS emergency_contacts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    student_id TEXT,
                    contact_name TEXT,
                    relationship TEXT,
                    phone_primary TEXT,
                    phone_secondary TEXT,
                    email TEXT,
                    address TEXT,
                    priority_order INTEGER,
                    medical_decision_maker INTEGER DEFAULT 0,
                    created_at TEXT,
                    FOREIGN KEY (student_id) REFERENCES students (student_id)
                );
