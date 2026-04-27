CREATE TABLE IF NOT EXISTS archived_book_loans (
                loan_id INTEGER PRIMARY KEY,
                book_id TEXT,
                user_id TEXT,
                checkout_date TEXT,
                due_date TEXT,
                return_date TEXT,
                status TEXT,
                fine_amount REAL DEFAULT 0,
                renewal_count INTEGER DEFAULT 0,
                reading_progress INTEGER DEFAULT 0,
                checkout_method TEXT,
                staff_id TEXT,
                notes TEXT,
                archived_at TEXT
            );
