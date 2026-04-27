CREATE TABLE IF NOT EXISTS peer_reviews (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    assignment_id INTEGER NOT NULL,
    reviewer_id INTEGER NOT NULL,
    reviewee_submission_id INTEGER NOT NULL,
    score REAL,
    feedback TEXT,
    rubric_scores TEXT,
    status TEXT DEFAULT 'pending',
    submitted_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP, reviewee_id TEXT,
    FOREIGN KEY (assignment_id) REFERENCES assignments (id),
    FOREIGN KEY (reviewer_id) REFERENCES users (id),
    FOREIGN KEY (reviewee_submission_id) REFERENCES assignment_submissions (id)
);
