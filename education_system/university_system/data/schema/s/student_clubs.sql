CREATE TABLE IF NOT EXISTS student_clubs (
                    club_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    club_name TEXT UNIQUE NOT NULL,
                    description TEXT,
                    category TEXT,
                    member_count INTEGER DEFAULT 0,
                    president_id TEXT,
                    treasurer_id TEXT,
                    secretary_id TEXT,
                    status TEXT DEFAULT 'active',
                    created_date TEXT, "budget" REAL DEFAULT 0.0, "founding_date" TEXT,
                    FOREIGN KEY (president_id) REFERENCES students (student_id),
                    FOREIGN KEY (treasurer_id) REFERENCES students (student_id),
                    FOREIGN KEY (secretary_id) REFERENCES students (student_id)
                );
