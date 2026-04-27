CREATE TABLE IF NOT EXISTS career_counseling (
            session_id INTEGER PRIMARY KEY AUTOINCREMENT,
            counselor_id TEXT,
            client_id TEXT,
            session_date TEXT,
            session_type TEXT,
            duration INTEGER,
            notes TEXT,
            status TEXT DEFAULT 'scheduled',
            follow_up_required BOOLEAN DEFAULT 0,
            FOREIGN KEY (counselor_id) REFERENCES alumni (alumni_id),
            FOREIGN KEY (client_id) REFERENCES alumni (alumni_id)
        );
