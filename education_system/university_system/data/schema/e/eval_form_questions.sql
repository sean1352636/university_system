CREATE TABLE IF NOT EXISTS eval_form_questions (
                id INTEGER PRIMARY KEY AUTOINCREMENT, form_id INTEGER NOT NULL,
                question_text TEXT NOT NULL, question_type TEXT DEFAULT 'rating',
                options TEXT, display_order INTEGER DEFAULT 0,
                is_required INTEGER DEFAULT 1,
                FOREIGN KEY (form_id) REFERENCES evaluation_forms(id));
