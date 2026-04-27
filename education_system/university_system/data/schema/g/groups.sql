CREATE TABLE IF NOT EXISTS groups (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                assignment_id INTEGER NOT NULL,
                group_name TEXT NOT NULL,
                created_at TEXT NOT NULL,
                created_by TEXT,
                is_active INTEGER DEFAULT 1,
                FOREIGN KEY (assignment_id) REFERENCES assignments (id),
                FOREIGN KEY (created_by) REFERENCES students (student_id)
            );
