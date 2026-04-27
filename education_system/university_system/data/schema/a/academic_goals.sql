CREATE TABLE IF NOT EXISTS academic_goals (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                student_id TEXT,
                parent_id TEXT,
                goal_title TEXT,
                description TEXT,
                target_grade TEXT,
                target_date TEXT,
                current_progress TEXT,
                status TEXT DEFAULT 'active',
                created_date TEXT,
                FOREIGN KEY (student_id) REFERENCES students (student_id),
                FOREIGN KEY (parent_id) REFERENCES parent_accounts (parent_id)
            );
