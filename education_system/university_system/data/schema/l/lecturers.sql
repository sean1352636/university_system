CREATE TABLE IF NOT EXISTS lecturers (
                lecturer_id INTEGER PRIMARY KEY AUTOINCREMENT,
                full_name   TEXT NOT NULL,
                department  TEXT NOT NULL,
                email       TEXT,
                title       TEXT
            );
