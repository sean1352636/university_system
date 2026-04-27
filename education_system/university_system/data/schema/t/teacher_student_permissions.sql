CREATE TABLE IF NOT EXISTS teacher_student_permissions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            teacher_id INTEGER,
            student_id TEXT,
            permission_type TEXT,
            FOREIGN KEY (teacher_id) REFERENCES users (id),
            FOREIGN KEY (student_id) REFERENCES students (student_id)
        );
