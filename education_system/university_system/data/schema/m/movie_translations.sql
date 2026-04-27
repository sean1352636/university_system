CREATE TABLE IF NOT EXISTS movie_translations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            movie_id INTEGER NOT NULL,
            language_code TEXT NOT NULL,
            title TEXT NOT NULL,
            description TEXT,
            FOREIGN KEY (movie_id) REFERENCES movies(id),
            UNIQUE(movie_id, language_code)
        );
