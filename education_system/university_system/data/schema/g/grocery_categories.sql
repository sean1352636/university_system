CREATE TABLE IF NOT EXISTS grocery_categories (
            category_id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            description TEXT,
            display_order INTEGER DEFAULT 0,
            is_active BOOLEAN DEFAULT 1,
            created_at TEXT NOT NULL
        );
