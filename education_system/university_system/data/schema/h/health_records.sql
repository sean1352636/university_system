CREATE TABLE IF NOT EXISTS health_records (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    student_id TEXT,
    record_type TEXT,
    record_date TEXT,
    description TEXT,
    provider TEXT,
    confidential INTEGER DEFAULT 0,
    created_at TEXT,
    encrypted_data TEXT
);
