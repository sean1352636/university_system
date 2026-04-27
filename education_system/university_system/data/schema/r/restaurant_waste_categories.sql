CREATE TABLE IF NOT EXISTS restaurant_waste_categories (
                category_id INTEGER PRIMARY KEY AUTOINCREMENT,
                category_name TEXT UNIQUE NOT NULL,
                description TEXT,
                target_percentage REAL,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            );
