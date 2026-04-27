CREATE TABLE IF NOT EXISTS student_budgets (
                        budget_id INTEGER PRIMARY KEY AUTOINCREMENT,
                        student_id TEXT NOT NULL,
                        budget_name TEXT NOT NULL,
                        budget_type TEXT CHECK(budget_type IN ('monthly', 'weekly', 'semester', 'annual', 'custom')),
                        start_date TEXT NOT NULL,
                        end_date TEXT NOT NULL,
                        total_income REAL DEFAULT 0.0,
                        total_budget REAL NOT NULL,
                        allocated_amount REAL DEFAULT 0.0,
                        spent_amount REAL DEFAULT 0.0,
                        is_active BOOLEAN DEFAULT 1,
                        notes TEXT,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        FOREIGN KEY (student_id) REFERENCES students(student_id)
                    );
