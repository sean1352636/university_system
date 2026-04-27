CREATE TABLE IF NOT EXISTS modules (
        module_id TEXT PRIMARY KEY,
        module_name TEXT NOT NULL,
        description TEXT,
        credits INTEGER DEFAULT 0,
        semester TEXT,
        year TEXT,
        instructor TEXT,
        department TEXT,
        prerequisites TEXT,
        is_active BOOLEAN DEFAULT 1,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP,
        updated_at TEXT DEFAULT CURRENT_TIMESTAMP
    , module_code TEXT, module_type TEXT DEFAULT 'Standard', "course" TEXT, "academic_year" TEXT);
