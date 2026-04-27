CREATE TABLE IF NOT EXISTS rideshare_posts (
                post_id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                post_type TEXT NOT NULL,
                departure_location TEXT NOT NULL,
                destination TEXT NOT NULL,
                departure_time TIMESTAMP NOT NULL,
                seats_available INTEGER,
                price_per_seat REAL,
                notes TEXT,
                status TEXT DEFAULT 'active',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP, "departure_date" TEXT, "id" INTEGER, "origin" TEXT, "trip_type" TEXT,
                FOREIGN KEY (user_id) REFERENCES users(id)
            );
