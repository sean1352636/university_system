CREATE TABLE IF NOT EXISTS police_evidence (
    id TEXT PRIMARY KEY,
    description TEXT,
    case_number TEXT,
    type TEXT,
    location TEXT,
    custody TEXT,
    date_added TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
