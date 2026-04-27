CREATE TABLE IF NOT EXISTS takeaway_addresses (
            address_id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            label TEXT DEFAULT 'Home',
            building TEXT,
            room_number TEXT,
            address_line TEXT NOT NULL,
            phone TEXT,
            is_default BOOLEAN DEFAULT 0,
            created_at TEXT NOT NULL,
            FOREIGN KEY (user_id) REFERENCES users (id)
        );
