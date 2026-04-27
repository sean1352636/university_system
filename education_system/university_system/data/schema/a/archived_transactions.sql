CREATE TABLE IF NOT EXISTS archived_transactions (
                    id INTEGER PRIMARY KEY,
                    student_id TEXT,
                    amount REAL,
                    transaction_type TEXT,
                    transaction_date TEXT,
                    description TEXT,
                    payment_method TEXT,
                    status TEXT,
                    archived_date TEXT DEFAULT CURRENT_TIMESTAMP
                );
