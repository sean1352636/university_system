CREATE TABLE IF NOT EXISTS peer_review_resource_ratings (
                    rating_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    resource_id INTEGER NOT NULL,
                    user_id TEXT NOT NULL,
                    rating INTEGER NOT NULL,
                    comment TEXT,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (resource_id) REFERENCES peer_review_shared_resources(resource_id),
                    UNIQUE(resource_id, user_id)
                );
