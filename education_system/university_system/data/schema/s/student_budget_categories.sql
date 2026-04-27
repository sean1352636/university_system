CREATE TABLE IF NOT EXISTS student_budget_categories (
                        category_id INTEGER PRIMARY KEY AUTOINCREMENT,
                        budget_id INTEGER NOT NULL,
                        category_name TEXT NOT NULL,
                        category_type TEXT CHECK(category_type IN ('essential', 'discretionary', 'savings', 'debt')),
                        allocated_amount REAL NOT NULL,
                        spent_amount REAL DEFAULT 0.0,
                        color_code TEXT,
                        icon TEXT,
                        notes TEXT,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        UNIQUE(budget_id, category_name)
                    );
