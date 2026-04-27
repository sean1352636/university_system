CREATE TABLE IF NOT EXISTS photo_gallery (
            photo_id INTEGER PRIMARY KEY AUTOINCREMENT,
            event_id INTEGER,
            uploaded_by TEXT,
            photo_path TEXT,
            caption TEXT,
            upload_date TEXT,
            is_featured BOOLEAN DEFAULT 0,
            FOREIGN KEY (event_id) REFERENCES alumni_events (event_id),
            FOREIGN KEY (uploaded_by) REFERENCES alumni (alumni_id)
        );
