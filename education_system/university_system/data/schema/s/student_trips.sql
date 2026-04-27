CREATE TABLE IF NOT EXISTS student_trips (
                                trip_id INTEGER PRIMARY KEY AUTOINCREMENT,
                                trip_name TEXT NOT NULL,
                                destination TEXT NOT NULL,
                                trip_date TEXT NOT NULL,
                                cost REAL NOT NULL,
                                max_participants INTEGER,
                                description TEXT,
                                organizing_club TEXT,
                                created_by INTEGER,
                                created_date TEXT DEFAULT CURRENT_TIMESTAMP
                            );
