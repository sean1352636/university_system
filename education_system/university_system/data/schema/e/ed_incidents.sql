CREATE TABLE IF NOT EXISTS ed_incidents (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        date_reported TEXT NOT NULL,
        category TEXT NOT NULL,
        department TEXT,
        description TEXT,
        status TEXT DEFAULT 'Open',
        reported_by TEXT
    , severity TEXT, sla_deadline TEXT, assigned_to TEXT, respondent TEXT, witnesses TEXT, outcome TEXT, resolution_category TEXT, lessons_learned TEXT, anonymous INTEGER DEFAULT 0, referred_to TEXT, referred_at TEXT);
