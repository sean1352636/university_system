CREATE TABLE IF NOT EXISTS meal_accounts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                student_id TEXT UNIQUE,
                balance DECIMAL(10,2) DEFAULT 0.00,
                low_balance_threshold DECIMAL(10,2) DEFAULT 10.00,
                auto_topup_enabled BOOLEAN DEFAULT 0,
                auto_topup_amount DECIMAL(10,2) DEFAULT 20.00,
                last_updated TEXT,
                FOREIGN KEY (student_id) REFERENCES students (student_id)
            );
