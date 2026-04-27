CREATE TABLE IF NOT EXISTS eval_form_responses (
                id INTEGER PRIMARY KEY AUTOINCREMENT, form_id INTEGER NOT NULL,
                student_hash TEXT NOT NULL, submitted_at TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (form_id) REFERENCES evaluation_forms(id));
