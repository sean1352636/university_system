CREATE TABLE IF NOT EXISTS trips (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                trip_name TEXT NOT NULL,
                description TEXT,
                destination TEXT NOT NULL,
                start_date TEXT NOT NULL,
                end_date TEXT NOT NULL,
                max_participants INTEGER DEFAULT 50,
                cost REAL DEFAULT 0.0,
                status TEXT DEFAULT 'planning',
                created_by INTEGER,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                FOREIGN KEY (created_by) REFERENCES users (id),
                CHECK (status IN ('planning', 'open', 'full', 'cancelled', 'completed'))
            );
