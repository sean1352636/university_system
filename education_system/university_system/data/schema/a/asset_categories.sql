CREATE TABLE IF NOT EXISTS asset_categories (
                category_id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE,
                description TEXT,
                depreciation_years INTEGER DEFAULT 5,
                requires_approval INTEGER DEFAULT 0,
                parent_category_id INTEGER,
                is_active INTEGER DEFAULT 1,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (parent_category_id) REFERENCES asset_categories(category_id)
            );
