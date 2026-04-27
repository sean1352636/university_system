CREATE TABLE IF NOT EXISTS evaluation_forms (
                id INTEGER PRIMARY KEY AUTOINCREMENT, module_code TEXT NOT NULL,
                module_name TEXT NOT NULL, academic_year TEXT NOT NULL, semester TEXT,
                status TEXT DEFAULT 'draft', created_by TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP, closes_at TEXT,
                is_anonymous INTEGER DEFAULT 1);
