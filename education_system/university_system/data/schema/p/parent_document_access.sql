CREATE TABLE IF NOT EXISTS parent_document_access (
    access_id INTEGER PRIMARY KEY AUTOINCREMENT,
    parent_id INTEGER NOT NULL,
    student_id INTEGER NOT NULL,
    document_id INTEGER,
    document_type TEXT,
    accessed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP, "id" INTEGER,
    FOREIGN KEY (parent_id) REFERENCES parent_accounts(parent_id),
    FOREIGN KEY (student_id) REFERENCES students(student_id)
);
