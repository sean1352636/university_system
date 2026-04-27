CREATE TABLE IF NOT EXISTS shared_academic_resources (
                resource_id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                subject TEXT,
                resource_type TEXT,
                description TEXT,
                file_path TEXT,
                uploaded_by TEXT,
                upload_date TEXT,
                downloads INTEGER DEFAULT 0
            );
