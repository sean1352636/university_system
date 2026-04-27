CREATE TABLE IF NOT EXISTS archived_payments (
                    id INTEGER PRIMARY KEY,
                    student_id TEXT,
                    amount REAL,
                    payment_date TEXT,
                    payment_method TEXT,
                    category TEXT,
                    status TEXT,
                    archived_date TEXT DEFAULT CURRENT_TIMESTAMP
                );
