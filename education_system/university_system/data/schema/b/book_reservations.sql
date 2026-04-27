CREATE TABLE IF NOT EXISTS book_reservations (
            reservation_id INTEGER PRIMARY KEY AUTOINCREMENT,
            book_id TEXT NOT NULL,
            user_id TEXT NOT NULL,
            reservation_date TEXT NOT NULL,
            expiry_date TEXT NOT NULL,
            status TEXT DEFAULT 'active',
            priority_order INTEGER DEFAULT 1,
            notification_sent BOOLEAN DEFAULT FALSE
        );
