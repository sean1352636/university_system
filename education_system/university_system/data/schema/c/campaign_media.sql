CREATE TABLE IF NOT EXISTS campaign_media (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    candidate_name TEXT,
                    file_name TEXT,
                    file_type TEXT,
                    file_path TEXT,
                    uploaded_by TEXT,
                    uploaded_at TEXT
                );
