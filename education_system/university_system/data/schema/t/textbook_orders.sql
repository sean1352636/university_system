CREATE TABLE IF NOT EXISTS textbook_orders (
                    order_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    listing_id INTEGER,
                    buyer_id TEXT NOT NULL,
                    seller_id TEXT NOT NULL,
                    price REAL NOT NULL,
                    status TEXT DEFAULT 'pending',
                    order_date TEXT DEFAULT (datetime('now')),
                    FOREIGN KEY (listing_id) REFERENCES textbook_listings(listing_id)
                );
