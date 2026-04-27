CREATE TABLE IF NOT EXISTS placement_review_signoffs (
                    signoff_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    review_id INTEGER NOT NULL,
                    signer_type TEXT NOT NULL,
                    signer_name TEXT NOT NULL,
                    signed_at TEXT DEFAULT (datetime('now')),
                    comments TEXT,
                    FOREIGN KEY (review_id) REFERENCES placement_reviews (review_id)
                );
