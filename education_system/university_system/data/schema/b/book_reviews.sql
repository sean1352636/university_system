CREATE TABLE IF NOT EXISTS book_reviews (
            review_id INTEGER PRIMARY KEY AUTOINCREMENT,
            book_id TEXT NOT NULL,
            user_id TEXT NOT NULL,
            rating INTEGER CHECK(rating >= 1 AND rating <= 5),
            review_text TEXT,
            review_date TEXT NOT NULL,
            status TEXT DEFAULT 'pending',
            helpful_votes INTEGER DEFAULT 0,
            moderated_by TEXT,
            moderation_date TEXT
        );
