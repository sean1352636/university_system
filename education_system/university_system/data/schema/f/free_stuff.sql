CREATE TABLE IF NOT EXISTS free_stuff (
                    item_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    giver_id TEXT NOT NULL,
                    item_name TEXT NOT NULL,
                    description TEXT NOT NULL,
                    category TEXT NOT NULL,
                    condition_status TEXT DEFAULT 'Used',
                    location TEXT NOT NULL,
                    pickup_instructions TEXT,
                    available_until TEXT,
                    contact_info TEXT,
                    status TEXT DEFAULT 'Available',
                    claimed_by TEXT,
                    claimed_at TEXT,
                    view_count INTEGER DEFAULT 0,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (giver_id) REFERENCES students(student_id)
                );
