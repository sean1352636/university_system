CREATE TABLE IF NOT EXISTS cinema_exclusive_screenings (
                    exclusive_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    screening_id INTEGER NOT NULL,
                    movie_title TEXT,
                    screening_date DATE,
                    screening_time TEXT,
                    description TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (screening_id) REFERENCES cinema_screenings(screening_id)
                );
