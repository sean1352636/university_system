CREATE TABLE IF NOT EXISTS club_media (
            media_id INTEGER PRIMARY KEY AUTOINCREMENT,
            club_id INTEGER,
            uploader_id TEXT,
            event_id INTEGER,
            file_path TEXT,
            file_type TEXT,
            caption TEXT,
            upload_date TEXT,
            FOREIGN KEY (club_id) REFERENCES student_clubs (club_id),
            FOREIGN KEY (uploader_id) REFERENCES students (student_id),
            FOREIGN KEY (event_id) REFERENCES union_events (event_id)
        );
