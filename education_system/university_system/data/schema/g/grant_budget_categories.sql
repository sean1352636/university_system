CREATE TABLE IF NOT EXISTS grant_budget_categories (
                    category_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL UNIQUE,
                    description TEXT,
                    is_active INTEGER DEFAULT 1,
                    sort_order INTEGER,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP
                );
