CREATE TABLE IF NOT EXISTS union_representatives (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id TEXT,
            position TEXT,
            department TEXT,
            election_date TEXT,
            term_end_date TEXT,
            status TEXT DEFAULT 'active',
            FOREIGN KEY (student_id) REFERENCES students (student_id)
        );
