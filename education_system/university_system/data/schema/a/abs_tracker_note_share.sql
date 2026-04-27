CREATE TABLE IF NOT EXISTS abs_tracker_note_share (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            owner_id     TEXT, module_code TEXT, date TEXT,
            file_path    TEXT, title TEXT,
            created_at   TEXT DEFAULT CURRENT_TIMESTAMP
        );
