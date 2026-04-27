CREATE TABLE IF NOT EXISTS restaurant_reservations (
                    reservation_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    customer_id INTEGER,
                    table_id INTEGER,
                    reservation_date TEXT NOT NULL,
                    reservation_time TEXT NOT NULL,
                    party_size INTEGER NOT NULL,
                    status TEXT DEFAULT 'Confirmed',
                    notes TEXT,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (customer_id) REFERENCES restaurant_customers(customer_id),
                    FOREIGN KEY (table_id) REFERENCES restaurant_tables(table_id)
                );
