CREATE TABLE IF NOT EXISTS tutor_group_members (
                    membership_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    group_id INTEGER NOT NULL,
                    student_id INTEGER NOT NULL,
                    role TEXT NOT NULL DEFAULT 'student',
                    joined_date TEXT NOT NULL,
                    left_date TEXT,
                    is_active INTEGER DEFAULT 1,
                    FOREIGN KEY (group_id) REFERENCES tutor_groups (group_id)
                );
