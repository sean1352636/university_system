CREATE TABLE IF NOT EXISTS ta_assignments (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id TEXT NOT NULL,
                    section_id TEXT,
                    module_code TEXT,
                    role TEXT NOT NULL DEFAULT 'ta' CHECK(role IN ('ta','co_instructor')),
                    can_grade INTEGER DEFAULT 0,
                    can_create_assignments INTEGER DEFAULT 0,
                    can_view_analytics INTEGER DEFAULT 0,
                    assigned_by TEXT,
                    assigned_at TEXT DEFAULT (datetime('now'))
                , hours_per_week REAL DEFAULT 0);
