CREATE TABLE IF NOT EXISTS homework_assignments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                student_id TEXT,
                module_code TEXT,
                assignment_title TEXT,
                description TEXT,
                assigned_date TEXT,
                due_date TEXT,
                completion_status TEXT DEFAULT 'pending',
                submitted_date TEXT,
                grade TEXT,
                teacher_comments TEXT,
                FOREIGN KEY (student_id) REFERENCES students (student_id),
                FOREIGN KEY (module_code) REFERENCES modules (module_code)
            );
