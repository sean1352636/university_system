CREATE TABLE IF NOT EXISTS budget_alerts (
                        alert_id INTEGER PRIMARY KEY AUTOINCREMENT,
                        student_id TEXT NOT NULL,
                        budget_id INTEGER,
                        category_id INTEGER,
                        alert_type TEXT CHECK(alert_type IN ('overspending', 'low-balance', 'goal-milestone', 'recurring-expense', 'custom')),
                        threshold_type TEXT CHECK(threshold_type IN ('percentage', 'amount')),
                        threshold_value REAL NOT NULL,
                        message TEXT NOT NULL,
                        is_active BOOLEAN DEFAULT 1,
                        last_triggered TEXT,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        FOREIGN KEY (student_id) REFERENCES students(student_id),
                        FOREIGN KEY (budget_id) REFERENCES student_budgets(budget_id),
                        FOREIGN KEY (category_id) REFERENCES budget_categories(category_id)
                    );
