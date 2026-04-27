CREATE TABLE IF NOT EXISTS cinema_screenings (
                    screening_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    movie_id INTEGER NOT NULL,
                    movie_title TEXT,
                    screen_number INTEGER,
                    screening_date DATE NOT NULL,
                    screening_time TEXT NOT NULL,
                    total_seats INTEGER DEFAULT 100,
                    available_seats INTEGER DEFAULT 100,
                    ticket_price REAL DEFAULT 12.00,
                    status TEXT DEFAULT 'available',
                    screen_type TEXT DEFAULT 'standard',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (movie_id) REFERENCES cinema_movies(movie_id)
                );
