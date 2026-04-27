CREATE TABLE IF NOT EXISTS committee_members (
                membership_id INTEGER PRIMARY KEY AUTOINCREMENT,
                committee_id INTEGER NOT NULL,
                user_id TEXT NOT NULL,
                user_name TEXT,
                role TEXT DEFAULT 'member',
                start_date TEXT,
                end_date TEXT,
                is_active INTEGER DEFAULT 1,
                notes TEXT,
                FOREIGN KEY (committee_id) REFERENCES committees(committee_id),
                UNIQUE(committee_id, user_id)
            );
