CREATE TABLE IF NOT EXISTS saved_listings (
                    saved_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id TEXT NOT NULL,
                    listing_type TEXT NOT NULL,
                    listing_id INTEGER NOT NULL,
                    notes TEXT,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (user_id) REFERENCES students(student_id)
                );
