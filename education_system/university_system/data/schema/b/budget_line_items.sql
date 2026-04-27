CREATE TABLE IF NOT EXISTS budget_line_items (
            line_item_id INTEGER PRIMARY KEY AUTOINCREMENT,
            budget_id INTEGER NOT NULL,
            category_id INTEGER NOT NULL,
            budgeted_amount DECIMAL(12,2) NOT NULL,
            actual_amount DECIMAL(12,2) DEFAULT 0,
            variance DECIMAL(12,2) DEFAULT 0,
            notes TEXT,
            created_at TEXT,
            updated_at TEXT,
            FOREIGN KEY (budget_id) REFERENCES budget_plans (budget_id),
            FOREIGN KEY (category_id) REFERENCES budget_categories (category_id)
        );
