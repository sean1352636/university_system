CREATE TABLE IF NOT EXISTS parent_messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                parent_id TEXT,
                teacher_id INTEGER,
                student_id TEXT,
                message_content TEXT,
                created_date TEXT,
                is_read BOOLEAN DEFAULT 0,
                is_from_parent BOOLEAN DEFAULT 1,
                message_type TEXT DEFAULT 'individual',
                group_id TEXT,
                FOREIGN KEY (parent_id) REFERENCES parent_accounts (parent_id),
                FOREIGN KEY (teacher_id) REFERENCES users (id),
                FOREIGN KEY (student_id) REFERENCES students (student_id)
            );
