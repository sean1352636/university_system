CREATE TABLE IF NOT EXISTS pastoral_assignments (
                    assignment_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    group_id INTEGER NOT NULL,
                    tutor_id INTEGER NOT NULL,
                    role TEXT NOT NULL DEFAULT 'personal_tutor',
                    assigned_date TEXT NOT NULL,
                    ended_date TEXT,
                    is_active INTEGER DEFAULT 1,
                    FOREIGN KEY (group_id) REFERENCES tutor_groups (group_id)
                );
