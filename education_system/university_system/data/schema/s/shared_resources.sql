CREATE TABLE IF NOT EXISTS shared_resources (
            resource_id INTEGER PRIMARY KEY AUTOINCREMENT,
            uploader_id TEXT,
            resource_title TEXT,
            resource_type TEXT,
            subject TEXT,
            file_path TEXT,
            description TEXT,
            upload_date TEXT,
            downloads INTEGER DEFAULT 0,
            rating REAL DEFAULT 0.0,
            FOREIGN KEY (uploader_id) REFERENCES students (student_id)
        );
