CREATE TABLE IF NOT EXISTS degree_course_prerequisites (
                prerequisite_id INTEGER PRIMARY KEY AUTOINCREMENT,
                module_code TEXT NOT NULL,
                prerequisite_module_code TEXT NOT NULL,
                min_grade TEXT,
                is_corequisite INTEGER DEFAULT 0,
                created_at TEXT NOT NULL DEFAULT (datetime('now')),
                UNIQUE(module_code, prerequisite_module_code)
            );
