CREATE TABLE IF NOT EXISTS payment_plan_installments (
            installment_id INTEGER PRIMARY KEY AUTOINCREMENT,
            payment_plan_id INTEGER NOT NULL,
            installment_number INTEGER NOT NULL,
            amount DECIMAL(10,2) NOT NULL,
            due_date TEXT NOT NULL,
            status TEXT DEFAULT 'pending', -- pending, paid, overdue, waived
            payment_id INTEGER,
            late_fee_amount DECIMAL(10,2) DEFAULT 0,
            created_at TEXT,
            updated_at TEXT,
            FOREIGN KEY (payment_plan_id) REFERENCES student_payment_plans (payment_plan_id),
            FOREIGN KEY (payment_id) REFERENCES "payments_old" (payment_id)
        );
