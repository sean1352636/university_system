CREATE TABLE IF NOT EXISTS academic_workshop_registrations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                workshop_id INTEGER,
                user_id TEXT,
                registered_at TEXT,
                attended INTEGER DEFAULT 0,
                FOREIGN KEY (workshop_id) REFERENCES academic_workshops (workshop_id)
            );
