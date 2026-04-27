CREATE TABLE IF NOT EXISTS parent_permissions (
    permission_id INTEGER PRIMARY KEY AUTOINCREMENT,
    link_id INTEGER NOT NULL,
    permission_type TEXT NOT NULL,  -- view_grades, view_attendance, view_financial
    granted BOOLEAN DEFAULT 1, "id" INTEGER, "parent_id" INTEGER, "student_id" TEXT, "granted_at" TEXT, "expires_at" TEXT,
    FOREIGN KEY (link_id) REFERENCES parent_student_links(link_id),
    UNIQUE(link_id, permission_type)
);
