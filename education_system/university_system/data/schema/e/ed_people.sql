CREATE TABLE IF NOT EXISTS ed_people (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ref_code TEXT UNIQUE NOT NULL,
        person_type TEXT NOT NULL,
        department TEXT,
        age_group TEXT,
        gender TEXT,
        ethnicity TEXT,
        disability TEXT,
        religion TEXT,
        sexual_orientation TEXT,
        nationality TEXT,
        date_added TEXT
    , user_id INTEGER, student_id TEXT, staff_id INTEGER, salary REAL, hours_per_week REAL, accommodations TEXT, self_updated_at TEXT, deleted_at TEXT, deleted_by TEXT, updated_at TEXT, updated_by TEXT, course TEXT, year_of_study INTEGER, programme_level TEXT, last_synced_at TEXT);
