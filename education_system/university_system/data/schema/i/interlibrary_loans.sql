CREATE TABLE IF NOT EXISTS interlibrary_loans (
            ill_id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT NOT NULL,
            title TEXT NOT NULL,
            author TEXT,
            isbn TEXT,
            source_library TEXT,
            request_date TEXT NOT NULL,
            expected_arrival TEXT,
            actual_arrival TEXT,
            due_date TEXT,
            return_date TEXT,
            status TEXT DEFAULT 'requested',
            cost REAL DEFAULT 0.0
        );
