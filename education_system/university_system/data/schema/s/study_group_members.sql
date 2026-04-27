CREATE TABLE IF NOT EXISTS study_group_members (
                    membership_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    group_id INTEGER NOT NULL,
                    student_id TEXT NOT NULL,
                    role TEXT DEFAULT 'Member',
                    joined_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    contribution_score INTEGER DEFAULT 0,
                    attendance_count INTEGER DEFAULT 0,
                    FOREIGN KEY (group_id) REFERENCES study_groups(group_id) ON DELETE CASCADE,
                    UNIQUE(group_id, student_id)
                );
