CREATE TABLE IF NOT EXISTS parent_portal_activity (
    activity_id INTEGER PRIMARY KEY AUTOINCREMENT,
    parent_id INTEGER NOT NULL,
    action_type TEXT NOT NULL,
    details TEXT,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    ip_address TEXT, "activity_type" TEXT, "created_at" TEXT, "description" TEXT, "id" INTEGER,
    FOREIGN KEY (parent_id) REFERENCES parent_accounts(parent_id)
);
