CREATE TABLE IF NOT EXISTS syllabi (
                    syllabus_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    module_code TEXT NOT NULL,
                    academic_year TEXT NOT NULL,
                    template_id INTEGER,
                    content_json TEXT NOT NULL,
                    status TEXT DEFAULT 'draft',
                    created_by TEXT,
                    reviewed_by TEXT,
                    review_date TEXT,
                    review_comments TEXT,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (template_id) REFERENCES syllabus_templates(template_id)
                );
