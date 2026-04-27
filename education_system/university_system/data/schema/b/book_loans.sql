CREATE TABLE IF NOT EXISTS book_loans (
            loan_id INTEGER PRIMARY KEY AUTOINCREMENT,
            book_id TEXT NOT NULL,
            user_id TEXT NOT NULL,
            checkout_date TEXT NOT NULL,
            due_date TEXT NOT NULL,
            return_date TEXT,
            status TEXT DEFAULT 'active',
            fine_amount REAL DEFAULT 0.0,
            renewal_count INTEGER DEFAULT 0,
            reading_progress INTEGER DEFAULT 0,
            checkout_method TEXT DEFAULT 'manual',
            staff_id TEXT,
            notes TEXT
        );
