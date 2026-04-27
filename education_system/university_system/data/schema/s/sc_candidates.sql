CREATE TABLE IF NOT EXISTS sc_candidates (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        student_id TEXT UNIQUE,
        name TEXT,
        position TEXT,
        platform TEXT,
        registered_at TEXT
    );
