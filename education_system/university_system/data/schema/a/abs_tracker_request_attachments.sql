CREATE TABLE IF NOT EXISTS abs_tracker_request_attachments (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            request_id  INTEGER,
            file_path   TEXT,
            uploaded_at TEXT DEFAULT CURRENT_TIMESTAMP
        );
