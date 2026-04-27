CREATE TABLE IF NOT EXISTS cinema_movies (
                    movie_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    title TEXT NOT NULL,
                    genre TEXT,
                    rating TEXT,
                    duration_minutes INTEGER,
                    description TEXT,
                    director TEXT,
                    cast TEXT,
                    release_date DATE,
                    status TEXT DEFAULT 'now_showing',
                    poster_url TEXT,
                    trailer_url TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
