CREATE TABLE IF NOT EXISTS marketplace_reviews (
                    review_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    listing_type TEXT NOT NULL,
                    listing_id INTEGER NOT NULL,
                    reviewer_id TEXT NOT NULL,
                    seller_id TEXT NOT NULL,
                    rating INTEGER NOT NULL,
                    review_text TEXT,
                    transaction_completed BOOLEAN DEFAULT 1,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (reviewer_id) REFERENCES students(student_id),
                    FOREIGN KEY (seller_id) REFERENCES students(student_id)
                );
