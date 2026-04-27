CREATE TABLE IF NOT EXISTS apprenticeships (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                employer_id INTEGER NOT NULL,
                description TEXT,
                duration_months INTEGER NOT NULL,
                salary REAL,
                location TEXT,
                required_course TEXT,
                min_year INTEGER DEFAULT 1,
                positions_available INTEGER DEFAULT 1,
                status TEXT DEFAULT 'Open',
                posted_date TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (employer_id) REFERENCES employers(id) ON DELETE CASCADE
            );
