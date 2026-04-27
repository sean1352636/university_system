CREATE TABLE IF NOT EXISTS time_entries (
                    entry_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id TEXT NOT NULL,
                    entry_date TEXT NOT NULL,
                    clock_in TEXT NOT NULL,
                    clock_out TEXT,
                    break_minutes INTEGER DEFAULT 0,
                    work_type TEXT DEFAULT 'regular',
                    location TEXT DEFAULT 'office',
                    notes TEXT,
                    is_manual BOOLEAN DEFAULT 0,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
                );
