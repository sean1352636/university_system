CREATE TABLE IF NOT EXISTS screenings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            movie_id INTEGER NOT NULL,
            screen_number INTEGER NOT NULL,
            show_time TEXT NOT NULL,
            price REAL NOT NULL,
            status TEXT DEFAULT 'active', is_3d INTEGER DEFAULT 0, is_imax INTEGER DEFAULT 0, social_distancing INTEGER DEFAULT 0,
            FOREIGN KEY (movie_id) REFERENCES movies(id)
        );
