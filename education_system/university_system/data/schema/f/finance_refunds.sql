CREATE TABLE IF NOT EXISTS finance_refunds (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        student_id TEXT,
                        refund_reference TEXT NOT NULL UNIQUE,
                        department TEXT NOT NULL,
                        transaction_id TEXT,
                        amount DECIMAL(10,2) NOT NULL,
                        refund_method TEXT NOT NULL,
                        refund_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        refund_time TEXT,
                        processed_by TEXT,
                        notes TEXT
                    );
