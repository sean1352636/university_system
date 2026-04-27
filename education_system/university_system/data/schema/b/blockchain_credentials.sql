CREATE TABLE IF NOT EXISTS blockchain_credentials (
    credential_id INTEGER PRIMARY KEY AUTOINCREMENT,
    student_id INTEGER NOT NULL,
    credential_type TEXT NOT NULL,  -- degree, certificate, diploma, transcript
    credential_name TEXT NOT NULL,
    issue_date DATE NOT NULL,
    blockchain_hash TEXT UNIQUE NOT NULL,
    blockchain_address TEXT,
    ipfs_hash TEXT,  -- For document storage
    metadata TEXT,  -- JSON
    is_revoked BOOLEAN DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (student_id) REFERENCES students(student_id)
);
