CREATE TABLE IF NOT EXISTS group_members (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                group_id INTEGER NOT NULL,
                student_id TEXT NOT NULL,
                role TEXT DEFAULT 'member',
                joined_at TEXT NOT NULL,
                contribution_score REAL DEFAULT 0,
                FOREIGN KEY (group_id) REFERENCES groups (id),
                FOREIGN KEY (student_id) REFERENCES students (student_id)
            );
