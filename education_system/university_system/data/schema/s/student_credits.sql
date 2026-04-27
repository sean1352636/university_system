CREATE TABLE IF NOT EXISTS student_credits (
            credit_id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id TEXT NOT NULL,
            credit_amount DECIMAL(10,2) NOT NULL,
            currency TEXT DEFAULT 'GBP',
            credit_source TEXT, -- 'overpayment', 'refund', 'scholarship', 'adjustment'
            description TEXT,
            expiry_date TEXT,
            remaining_amount DECIMAL(10,2) NOT NULL,
            status TEXT DEFAULT 'active', -- active, used, expired
            created_by TEXT,
            created_at TEXT,
            updated_at TEXT,
            FOREIGN KEY (student_id) REFERENCES students (student_id)
        );
