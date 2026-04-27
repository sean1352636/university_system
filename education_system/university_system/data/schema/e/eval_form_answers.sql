CREATE TABLE IF NOT EXISTS eval_form_answers (
                id INTEGER PRIMARY KEY AUTOINCREMENT, response_id INTEGER NOT NULL,
                question_id INTEGER NOT NULL, rating_value INTEGER, text_value TEXT,
                FOREIGN KEY (response_id) REFERENCES eval_form_responses(id),
                FOREIGN KEY (question_id) REFERENCES eval_form_questions(id));
