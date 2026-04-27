CREATE TABLE IF NOT EXISTS security_desk_tickets (
    id TEXT PRIMARY KEY,
    type TEXT,
    category TEXT,
    priority TEXT DEFAULT 'Normal',
    status TEXT DEFAULT 'Open',
    subject TEXT,
    description TEXT,
    location TEXT,
    user_id TEXT,
    user_name TEXT,
    user_email TEXT,
    admin_notes TEXT,
    created_at TEXT,
    updated_at TEXT
);
