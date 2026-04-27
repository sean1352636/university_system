CREATE TABLE IF NOT EXISTS student_income (
                        income_id INTEGER PRIMARY KEY AUTOINCREMENT,
                        student_id TEXT NOT NULL,
                        budget_id INTEGER,
                        income_date TEXT NOT NULL,
                        amount REAL NOT NULL,
                        source TEXT NOT NULL,
                        income_type TEXT CHECK(income_type IN ('work-study', 'scholarship', 'grant', 'loan', 'family', 'job', 'investment', 'other')),
                        description TEXT,
                        is_recurring BOOLEAN DEFAULT 0,
                        recurrence_pattern TEXT,
                        notes TEXT,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        FOREIGN KEY (student_id) REFERENCES students(student_id),
                        FOREIGN KEY (budget_id) REFERENCES student_budgets(budget_id)
                    );
