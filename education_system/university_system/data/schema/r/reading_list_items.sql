CREATE TABLE IF NOT EXISTS reading_list_items (
            item_id INTEGER PRIMARY KEY AUTOINCREMENT,
            list_id INTEGER NOT NULL,
            book_id TEXT NOT NULL,
            added_date TEXT NOT NULL,
            added_by TEXT NOT NULL,
            notes TEXT,
            order_index INTEGER DEFAULT 0
        );
