CREATE TABLE IF NOT EXISTS musicshop_wishlist (
    wishlist_id INTEGER PRIMARY KEY AUTOINCREMENT,
    customer_name TEXT NOT NULL,
    product_id INTEGER NOT NULL,
    added_date TEXT NOT NULL,
    FOREIGN KEY (product_id) REFERENCES products (product_id)
);
