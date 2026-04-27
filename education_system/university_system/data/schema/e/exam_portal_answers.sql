CREATE TABLE IF NOT EXISTS exam_portal_answers (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    attempt_id      INTEGER NOT NULL,
    question_id     INTEGER NOT NULL,
    answer_text     TEXT,
    is_correct      INTEGER,
    marks_awarded   REAL,
    feedback        TEXT,
    flagged         INTEGER DEFAULT 0,
    time_spent_secs INTEGER DEFAULT 0,
    answered_at     TEXT    DEFAULT (datetime('now')),
    FOREIGN KEY (attempt_id) REFERENCES exam_portal_attempts(id),
    FOREIGN KEY (question_id) REFERENCES exam_portal_questions(id)
);
