CREATE TABLE IF NOT EXISTS library_payments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                receipt_id TEXT UNIQUE,
                user_id TEXT,
                amount REAL,
                payment_method TEXT,
                payment_date TEXT
            );
