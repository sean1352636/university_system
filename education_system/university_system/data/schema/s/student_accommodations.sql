CREATE TABLE IF NOT EXISTS student_accommodations (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    student_id TEXT NOT NULL,
                    accommodation_type TEXT NOT NULL CHECK(accommodation_type IN ('extended_time','alt_format','screen_reader','large_text','other')),
                    details TEXT,
                    time_multiplier REAL DEFAULT 1.0,
                    is_active INTEGER DEFAULT 1,
                    approved_by TEXT,
                    created_at TEXT DEFAULT (datetime('now')),
                    expires_at TEXT
                );
