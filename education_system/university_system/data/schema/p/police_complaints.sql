CREATE TABLE IF NOT EXISTS police_complaints (
    id TEXT PRIMARY KEY,
    complainant TEXT,
    email TEXT,
    phone TEXT,
    type TEXT,
    priority TEXT DEFAULT 'Medium',
    status TEXT DEFAULT 'Pending',
    incident_date TEXT,
    incident_time TEXT,
    location TEXT,
    description TEXT,
    suspect_description TEXT,
    date TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
