CREATE TABLE IF NOT EXISTS parent_conference_requests (
    request_id INTEGER PRIMARY KEY AUTOINCREMENT,
    parent_id INTEGER NOT NULL,
    teacher_id INTEGER NOT NULL,
    student_id INTEGER NOT NULL,
    preferred_times TEXT,  -- JSON array
    reason TEXT,
    status TEXT DEFAULT 'pending',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP, "id" INTEGER, "instructor_id" INTEGER, "requested_date" TEXT, "preferred_time" TEXT,
    FOREIGN KEY (parent_id) REFERENCES parent_accounts(parent_id)
);
