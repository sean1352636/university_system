CREATE TABLE IF NOT EXISTS assignment_group_members (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                group_id INTEGER NOT NULL,
                student_id INTEGER NOT NULL,
                role TEXT DEFAULT 'member',
                joined_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (group_id) REFERENCES assignment_groups(id),
                FOREIGN KEY (student_id) REFERENCES users(id)
            );
