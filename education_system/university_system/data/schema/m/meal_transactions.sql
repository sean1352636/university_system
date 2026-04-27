CREATE TABLE IF NOT EXISTS meal_transactions (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        student_id TEXT,
                        transaction_type TEXT,
                        amount DECIMAL(10,2),
                        description TEXT,
                        transaction_date TEXT,
                        balance_after DECIMAL(10,2),
                        FOREIGN KEY (student_id) REFERENCES students (student_id)
                    );
