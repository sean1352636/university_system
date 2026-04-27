CREATE TABLE IF NOT EXISTS academic_study_group_members (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                group_id INTEGER,
                user_id TEXT,
                joined_at TEXT,
                FOREIGN KEY (group_id) REFERENCES academic_study_groups (group_id)
            );
