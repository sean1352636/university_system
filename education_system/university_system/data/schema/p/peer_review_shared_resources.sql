CREATE TABLE IF NOT EXISTS peer_review_shared_resources (
                    resource_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    title TEXT NOT NULL,
                    description TEXT,
                    resource_type TEXT DEFAULT 'template',
                    subject_area TEXT,
                    course_code TEXT,
                    file_path TEXT,
                    file_name TEXT,
                    shared_by TEXT NOT NULL,
                    download_count INTEGER DEFAULT 0,
                    rating_sum INTEGER DEFAULT 0,
                    rating_count INTEGER DEFAULT 0,
                    is_approved INTEGER DEFAULT 0,
                    status TEXT DEFAULT 'active',
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
                );
