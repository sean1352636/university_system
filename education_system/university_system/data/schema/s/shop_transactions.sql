CREATE TABLE IF NOT EXISTS shop_transactions (
                    transaction_id TEXT PRIMARY KEY,
                    user_id INTEGER,
                    student_id TEXT,
                    total_amount REAL NOT NULL,
                    transaction_date TEXT NOT NULL,
                    payment_method TEXT,
                    status TEXT NOT NULL,
                    notes TEXT,
                    FOREIGN KEY (user_id) REFERENCES users (id),
                    FOREIGN KEY (student_id) REFERENCES students (student_id)
                );
