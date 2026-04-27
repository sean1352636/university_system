CREATE TABLE IF NOT EXISTS musicshop_wishlists (
        wishlist_id INTEGER PRIMARY KEY AUTOINCREMENT,
        customer_id TEXT NOT NULL,
        product_id INTEGER NOT NULL,
        added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (product_id) REFERENCES musicshop_products(product_id),
        UNIQUE(customer_id, product_id)
    );
