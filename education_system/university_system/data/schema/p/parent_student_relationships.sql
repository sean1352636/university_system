CREATE TABLE IF NOT EXISTS parent_student_relationships (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            parent_id TEXT,
            student_id TEXT,
            relationship_type TEXT,
            access_level TEXT DEFAULT 'full',
            date_added TEXT,
            FOREIGN KEY (parent_id) REFERENCES parent_accounts (parent_id),
            FOREIGN KEY (student_id) REFERENCES students (student_id)
        );
