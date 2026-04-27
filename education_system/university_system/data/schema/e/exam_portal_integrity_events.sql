CREATE TABLE IF NOT EXISTS exam_portal_integrity_events (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    attempt_id      INTEGER NOT NULL,
    event_type      TEXT    NOT NULL,
    event_data      TEXT,
    created_at      TEXT    NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (attempt_id) REFERENCES exam_portal_attempts(id)
);
