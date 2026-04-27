CREATE TABLE IF NOT EXISTS exam_portal_questions (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    exam_id         INTEGER NOT NULL,
    question_type   TEXT    NOT NULL DEFAULT 'mcq',
    question_text   TEXT    NOT NULL,
    options_json    TEXT,
    correct_answer  TEXT,
    marks           REAL    NOT NULL DEFAULT 1.0,
    order_index     INTEGER DEFAULT 0,
    explanation     TEXT,
    difficulty      TEXT    DEFAULT 'medium',
    created_at      TEXT    NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (exam_id) REFERENCES exam_portal_exams(id)
);
