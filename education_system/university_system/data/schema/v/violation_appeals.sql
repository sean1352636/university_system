CREATE TABLE IF NOT EXISTS violation_appeals (
    appeal_id INTEGER PRIMARY KEY AUTOINCREMENT,
    violation_id INTEGER NOT NULL,
    reason TEXT NOT NULL,
    supporting_documents TEXT,  -- JSON array
    status TEXT DEFAULT 'pending',
    submitted_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    reviewed_by INTEGER,
    review_date TIMESTAMP,
    decision TEXT, "id" INTEGER, "appealed_by" INTEGER, "appeal_reason" TEXT, "appeal_date" TEXT, "review_notes" TEXT,
    FOREIGN KEY (violation_id) REFERENCES parking_violations(violation_id)
);
