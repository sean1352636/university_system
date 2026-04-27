CREATE TABLE IF NOT EXISTS archived_budget_records (
                    id INTEGER PRIMARY KEY,
                    department TEXT,
                    category TEXT,
                    allocated_amount REAL,
                    spent_amount REAL,
                    fiscal_year TEXT,
                    archived_date TEXT DEFAULT CURRENT_TIMESTAMP
                );
