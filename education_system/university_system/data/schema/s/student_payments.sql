CREATE TABLE IF NOT EXISTS student_payments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                fee_id INTEGER,
                student_id TEXT NOT NULL,
                amount_paid REAL NOT NULL,
                payment_method TEXT,
                reference TEXT,
                payment_date TEXT DEFAULT (date('now'))
            );
