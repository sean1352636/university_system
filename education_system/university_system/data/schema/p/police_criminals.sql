CREATE TABLE IF NOT EXISTS police_criminals (
    id TEXT PRIMARY KEY,
    name TEXT,
    crime TEXT,
    status TEXT,
    arrest_date TEXT,
    case_number TEXT,
    description TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
