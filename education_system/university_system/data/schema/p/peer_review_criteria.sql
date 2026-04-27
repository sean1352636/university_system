CREATE TABLE IF NOT EXISTS peer_review_criteria (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            review_id INTEGER NOT NULL,
            criteria_name TEXT NOT NULL,
            score INTEGER NOT NULL,
            comment TEXT,
            FOREIGN KEY (review_id) REFERENCES peer_reviews (id)
        );
