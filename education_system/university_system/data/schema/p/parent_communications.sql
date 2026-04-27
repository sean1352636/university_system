CREATE TABLE IF NOT EXISTS parent_communications (
    comm_id INTEGER PRIMARY KEY AUTOINCREMENT,
    parent_id INTEGER NOT NULL,
    staff_id INTEGER,
    student_id INTEGER,
    subject TEXT,
    message TEXT NOT NULL,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    is_read BOOLEAN DEFAULT 0, "content" TEXT, "id" INTEGER, "read_at" TEXT, "sent_at" TEXT, "type" TEXT,
    FOREIGN KEY (parent_id) REFERENCES parent_accounts(parent_id)
);
