CREATE TABLE IF NOT EXISTS book_requests (
            request_id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT NOT NULL,
            title TEXT NOT NULL,
            author TEXT,
            isbn TEXT,
            reason TEXT,
            status TEXT DEFAULT 'pending',
            priority INTEGER DEFAULT 1,
            requested_date TEXT NOT NULL,
            processed_date TEXT,
            processed_by TEXT,
            notes TEXT
        );
