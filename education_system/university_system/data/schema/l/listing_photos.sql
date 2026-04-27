CREATE TABLE IF NOT EXISTS listing_photos (
                    photo_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    listing_type TEXT NOT NULL,
                    listing_id INTEGER NOT NULL,
                    photo_path TEXT NOT NULL,
                    is_primary BOOLEAN DEFAULT 0,
                    caption TEXT,
                    uploaded_at TEXT DEFAULT CURRENT_TIMESTAMP
                );
