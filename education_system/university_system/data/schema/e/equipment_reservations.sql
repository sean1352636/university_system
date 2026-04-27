CREATE TABLE IF NOT EXISTS equipment_reservations (
                    reservation_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    item_id INTEGER NOT NULL,
                    borrower_id TEXT NOT NULL,
                    borrower_name TEXT NOT NULL,
                    requested_date TEXT NOT NULL,
                    requested_duration INTEGER DEFAULT 1,
                    status TEXT DEFAULT 'pending',
                    priority INTEGER DEFAULT 5,
                    notes TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (item_id) REFERENCES equipment_items(item_id)
                );
