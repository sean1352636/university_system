CREATE TABLE IF NOT EXISTS support_group_members (
            membership_id INTEGER PRIMARY KEY AUTOINCREMENT,
            group_id INTEGER,
            student_id TEXT,
            join_date TEXT,
            anonymous_id TEXT,
            status TEXT DEFAULT 'active',
            FOREIGN KEY (group_id) REFERENCES peer_support_groups (group_id),
            FOREIGN KEY (student_id) REFERENCES students (student_id)
        );
