CREATE TABLE IF NOT EXISTS evaluation_questions (
                question_id INTEGER PRIMARY KEY AUTOINCREMENT,
                template_id INTEGER NOT NULL,
                question_text TEXT NOT NULL,
                question_type TEXT NOT NULL,
                question_category TEXT,
                scale_min INTEGER DEFAULT 1,
                scale_max INTEGER DEFAULT 5,
                display_order INTEGER DEFAULT 0,
                is_required INTEGER DEFAULT 1, "options" TEXT,
                FOREIGN KEY (template_id) REFERENCES evaluation_templates(template_id) ON DELETE CASCADE
            );
