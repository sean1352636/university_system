CREATE TABLE IF NOT EXISTS movie_series_link (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            movie_id INTEGER NOT NULL,
            series_id INTEGER NOT NULL,
            sequence_number INTEGER DEFAULT 1,
            FOREIGN KEY (movie_id) REFERENCES movies(id),
            FOREIGN KEY (series_id) REFERENCES movie_series(id),
            UNIQUE(movie_id, series_id)
        );
