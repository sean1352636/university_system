CREATE TABLE IF NOT EXISTS course_evaluations (
                evaluation_id INTEGER PRIMARY KEY AUTOINCREMENT,
                module_code TEXT NOT NULL,
                academic_year TEXT NOT NULL,
                semester TEXT NOT NULL,
                instructor_id TEXT NOT NULL,
                template_id INTEGER NOT NULL,
                start_date TEXT NOT NULL,
                end_date TEXT NOT NULL,
                response_count INTEGER DEFAULT 0,
                is_active INTEGER DEFAULT 1,
                created_at TEXT NOT NULL DEFAULT (datetime('now')), "completion_rate" REAL DEFAULT 0, "is_anonymous" BOOLEAN DEFAULT 1,
                FOREIGN KEY (template_id) REFERENCES evaluation_templates(template_id)
            );
