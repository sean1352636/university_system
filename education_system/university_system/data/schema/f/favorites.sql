CREATE TABLE IF NOT EXISTS favorites (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            member_id INTEGER,
            customer_email TEXT,
            movie_id INTEGER NOT NULL,
            added_at TEXT DEFAULT CURRENT_TIMESTAMP,
            notify_screenings INTEGER DEFAULT 1,
            FOREIGN KEY (member_id) REFERENCES members(id),
            FOREIGN KEY (movie_id) REFERENCES movies(id),
            UNIQUE(customer_email, movie_id)
        );
