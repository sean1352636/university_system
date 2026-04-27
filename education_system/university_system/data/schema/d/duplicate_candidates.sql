CREATE TABLE IF NOT EXISTS duplicate_candidates (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id_1 TEXT,
            student_id_2 TEXT,
            similarity_score REAL,
            status TEXT DEFAULT 'pending',
            reviewed_by TEXT,
            reviewed_date DATETIME
        );
