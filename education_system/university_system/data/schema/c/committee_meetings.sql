CREATE TABLE IF NOT EXISTS committee_meetings (
                    meeting_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    committee_id INTEGER NOT NULL,
                    title TEXT NOT NULL,
                    meeting_date TEXT NOT NULL,
                    start_time TEXT NOT NULL,
                    end_time TEXT,
                    location TEXT,
                    virtual_link TEXT,
                    status TEXT DEFAULT 'scheduled',
                    chair_id TEXT,
                    secretary_id TEXT,
                    recurrence TEXT DEFAULT 'none',
                    notes TEXT,
                    created_by TEXT,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (committee_id) REFERENCES committees(committee_id)
                );
