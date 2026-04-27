CREATE TABLE IF NOT EXISTS ambassador_program (
            ambassador_id INTEGER PRIMARY KEY AUTOINCREMENT,
            alumni_id TEXT,
            start_date TEXT,
            end_date TEXT,
            status TEXT DEFAULT 'active',
            region TEXT,
            activities TEXT,
            performance_score REAL DEFAULT 0.0,
            FOREIGN KEY (alumni_id) REFERENCES alumni (alumni_id)
        );
