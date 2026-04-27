CREATE TABLE IF NOT EXISTS late_fees (
            late_fee_id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_fee_id INTEGER NOT NULL,
            late_fee_amount DECIMAL(10,2) NOT NULL,
            calculation_method TEXT, -- 'fixed', 'percentage', 'daily'
            days_overdue INTEGER NOT NULL,
            applied_date TEXT NOT NULL,
            waived BOOLEAN DEFAULT 0,
            waived_by TEXT,
            waived_date TEXT,
            waiver_reason TEXT,
            created_at TEXT,
            FOREIGN KEY (student_fee_id) REFERENCES student_fees (student_fee_id)
        );
