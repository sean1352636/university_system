CREATE TABLE IF NOT EXISTS hours_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                student_id INTEGER NOT NULL,
                log_date TEXT NOT NULL,
                hours REAL NOT NULL,
                activity TEXT,
                supervisor_signoff INTEGER DEFAULT 0,
                notes TEXT,
                FOREIGN KEY (student_id) REFERENCES students(id) ON DELETE CASCADE
            );
