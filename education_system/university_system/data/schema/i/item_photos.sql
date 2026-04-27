CREATE TABLE IF NOT EXISTS item_photos (
                    photo_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    item_type TEXT NOT NULL,
                    item_id INTEGER NOT NULL,
                    photo_path TEXT NOT NULL,
                    photo_hash TEXT,
                    caption TEXT,
                    uploaded_at TEXT DEFAULT CURRENT_TIMESTAMP
                );
