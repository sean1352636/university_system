CREATE TABLE IF NOT EXISTS police_cases (
    id TEXT PRIMARY KEY,
    title TEXT,
    type TEXT,
    status TEXT DEFAULT 'Open',
    priority TEXT DEFAULT 'Medium',
    officer TEXT,
    location TEXT,
    description TEXT,
    notes TEXT,
    witnesses TEXT,
    date TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
