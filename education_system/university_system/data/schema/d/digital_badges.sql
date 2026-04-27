CREATE TABLE IF NOT EXISTS digital_badges (
    badge_id INTEGER PRIMARY KEY AUTOINCREMENT,
    badge_name TEXT NOT NULL,
    description TEXT,
    criteria TEXT NOT NULL,
    badge_image_url TEXT,
    issuer_name TEXT NOT NULL,
    badge_type TEXT DEFAULT 'skill',  -- skill, achievement, completion
    is_active BOOLEAN DEFAULT 1,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
