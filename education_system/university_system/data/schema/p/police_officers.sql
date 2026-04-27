CREATE TABLE IF NOT EXISTS police_officers (
    badge TEXT PRIMARY KEY,
    name TEXT,
    rank TEXT,
    department TEXT,
    status TEXT DEFAULT 'Active',
    phone TEXT,
    email TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
