CREATE TABLE IF NOT EXISTS parent_teacher_meetings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                parent_id TEXT,
                teacher_id INTEGER,
                student_id TEXT,
                meeting_date TEXT,
                start_time TEXT,
                end_time TEXT,
                location TEXT,
                meeting_type TEXT,
                status TEXT DEFAULT 'scheduled',
                agenda TEXT,
                notes TEXT,
                FOREIGN KEY (parent_id) REFERENCES parent_accounts (parent_id),
                FOREIGN KEY (teacher_id) REFERENCES users (id),
                FOREIGN KEY (student_id) REFERENCES students (student_id)
            );
