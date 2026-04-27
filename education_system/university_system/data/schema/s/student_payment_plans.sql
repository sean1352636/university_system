CREATE TABLE IF NOT EXISTS student_payment_plans (
            payment_plan_id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id TEXT NOT NULL,
            template_id INTEGER,
            total_amount DECIMAL(10,2) NOT NULL,
            remaining_amount DECIMAL(10,2) NOT NULL,
            currency TEXT DEFAULT 'GBP',
            status TEXT DEFAULT 'active', -- active, completed, defaulted, cancelled
            start_date TEXT NOT NULL,
            next_due_date TEXT,
            setup_fee_paid BOOLEAN DEFAULT 0,
            auto_payment_enabled BOOLEAN DEFAULT 0,
            payment_method_id INTEGER,
            notes TEXT,
            created_at TEXT,
            updated_at TEXT,
            FOREIGN KEY (student_id) REFERENCES students (student_id),
            FOREIGN KEY (template_id) REFERENCES payment_plan_templates (template_id)
        );
