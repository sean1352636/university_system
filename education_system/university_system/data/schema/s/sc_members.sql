CREATE TABLE IF NOT EXISTS sc_members (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        student_id TEXT UNIQUE,
        name TEXT,
        email TEXT,
        department TEXT,
        position TEXT,
        joined_at TEXT
    );
