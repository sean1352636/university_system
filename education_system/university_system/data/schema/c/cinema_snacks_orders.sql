CREATE TABLE IF NOT EXISTS cinema_snacks_orders (
                    order_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    booking_id INTEGER,
                    booking_ref TEXT,
                    user_id TEXT NOT NULL,
                    snack_item TEXT NOT NULL,
                    quantity INTEGER NOT NULL,
                    unit_price REAL NOT NULL,
                    subtotal REAL NOT NULL,
                    is_combo BOOLEAN DEFAULT 0,
                    order_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (booking_id) REFERENCES cinema_bookings(booking_id)
                );
