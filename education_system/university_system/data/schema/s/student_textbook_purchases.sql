CREATE TABLE IF NOT EXISTS student_textbook_purchases (
                        purchase_id INTEGER PRIMARY KEY AUTOINCREMENT,
                        student_id TEXT NOT NULL,
                        listing_id INTEGER,
                        isbn TEXT NOT NULL,
                        title TEXT NOT NULL,
                        course_code TEXT,
                        purchase_date TEXT NOT NULL,
                        vendor TEXT NOT NULL,
                        purchase_type TEXT CHECK(purchase_type IN ('buy-new', 'buy-used', 'rent', 'digital')),
                        price_paid REAL NOT NULL,
                        condition TEXT,
                        rental_due_date TEXT,
                        resale_value REAL,
                        notes TEXT,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        FOREIGN KEY (student_id) REFERENCES students(student_id),
                        FOREIGN KEY (listing_id) REFERENCES textbook_listings(listing_id)
                    );
