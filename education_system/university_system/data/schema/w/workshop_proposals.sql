CREATE TABLE IF NOT EXISTS workshop_proposals (
                proposal_id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                category TEXT,
                duration_hours REAL,
                level TEXT,
                max_participants INTEGER,
                description TEXT,
                prerequisites TEXT,
                proposed_by TEXT,
                proposed_date TEXT,
                status TEXT DEFAULT 'pending'
            );
