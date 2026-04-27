CREATE TABLE IF NOT EXISTS badge_issuances (
    issuance_id INTEGER PRIMARY KEY AUTOINCREMENT,
    badge_id INTEGER NOT NULL,
    student_id INTEGER NOT NULL,
    issued_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    blockchain_hash TEXT,
    evidence_url TEXT,
    expires_at DATE,
    is_revoked BOOLEAN DEFAULT 0,
    FOREIGN KEY (badge_id) REFERENCES digital_badges(badge_id),
    FOREIGN KEY (student_id) REFERENCES students(student_id)
);
