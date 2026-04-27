CREATE TABLE IF NOT EXISTS donor_recognition (
            recognition_id INTEGER PRIMARY KEY AUTOINCREMENT,
            alumni_id TEXT,
            recognition_level TEXT,
            total_donated REAL,
            recognition_date TEXT,
            benefits TEXT,
            FOREIGN KEY (alumni_id) REFERENCES alumni (alumni_id)
        );
