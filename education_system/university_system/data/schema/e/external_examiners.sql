CREATE TABLE IF NOT EXISTS external_examiners (
                examiner_id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                institution TEXT,
                email TEXT,
                phone TEXT,
                expertise_area TEXT,
                department TEXT,
                appointment_start TEXT,
                appointment_end TEXT,
                status TEXT DEFAULT 'active',
                contact_person_id TEXT,
                notes TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            );
