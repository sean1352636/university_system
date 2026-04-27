CREATE TABLE IF NOT EXISTS parent_student_links (
    link_id INTEGER PRIMARY KEY AUTOINCREMENT,
    parent_id INTEGER NOT NULL,
    student_id INTEGER NOT NULL,
    relationship TEXT NOT NULL,  -- parent, guardian, other
    permissions TEXT,  -- JSON
    is_primary BOOLEAN DEFAULT 0,
    verified BOOLEAN DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP, "id" INTEGER, "is_primary_contact" INTEGER DEFAULT 0, "can_view_grades" INTEGER DEFAULT 1, "can_view_attendance" INTEGER DEFAULT 1, "can_view_finances" INTEGER DEFAULT 0,
    FOREIGN KEY (parent_id) REFERENCES parent_accounts(parent_id),
    FOREIGN KEY (student_id) REFERENCES students(student_id),
    UNIQUE(parent_id, student_id)
);
