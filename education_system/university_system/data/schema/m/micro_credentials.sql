CREATE TABLE IF NOT EXISTS micro_credentials (
    micro_id INTEGER PRIMARY KEY AUTOINCREMENT,
    skill_name TEXT NOT NULL,
    description TEXT,
    criteria TEXT NOT NULL,
    points INTEGER DEFAULT 1,
    category TEXT,  -- technical, soft_skills, academic
    is_stackable BOOLEAN DEFAULT 1,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
