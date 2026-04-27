CREATE TABLE IF NOT EXISTS expense_categories (
                    category_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL UNIQUE,
                    description TEXT,
                    max_amount REAL,
                    requires_receipt BOOLEAN DEFAULT 1,
                    requires_approval BOOLEAN DEFAULT 1,
                    approval_threshold REAL,
                    is_active BOOLEAN DEFAULT 1,
                    gl_code TEXT,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP
                );
