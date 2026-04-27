CREATE TABLE IF NOT EXISTS student_financial_aid (
            aid_id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id TEXT NOT NULL,
            aid_type_id INTEGER NOT NULL,
            awarded_amount DECIMAL(10,2) NOT NULL,
            disbursed_amount DECIMAL(10,2) DEFAULT 0,
            remaining_amount DECIMAL(10,2) NOT NULL,
            currency TEXT DEFAULT 'GBP',
            status TEXT DEFAULT 'pending', -- pending, approved, disbursed, completed, cancelled
            application_date TEXT,
            approval_date TEXT,
            disbursement_schedule TEXT, -- JSON with disbursement dates and amounts
            repayment_start_date TEXT,
            monthly_payment_amount DECIMAL(10,2),
            total_repaid DECIMAL(10,2) DEFAULT 0,
            approved_by TEXT,
            notes TEXT,
            created_at TEXT,
            updated_at TEXT,
            FOREIGN KEY (student_id) REFERENCES students (student_id),
            FOREIGN KEY (aid_type_id) REFERENCES financial_aid_types (aid_type_id)
        );
