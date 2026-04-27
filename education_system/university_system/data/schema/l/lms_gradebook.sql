CREATE TABLE IF NOT EXISTS lms_gradebook (
                entry_id INTEGER PRIMARY KEY AUTOINCREMENT,
                lms_course_id INTEGER NOT NULL,
                student_id TEXT NOT NULL,
                assignment_type TEXT NOT NULL,
                assignment_id INTEGER NOT NULL,
                score REAL NOT NULL,
                max_score REAL NOT NULL,
                weight REAL DEFAULT 1.0,
                feedback TEXT,
                graded_by TEXT,
                graded_at TEXT NOT NULL DEFAULT (datetime('now')), "created_at" TEXT DEFAULT CURRENT_TIMESTAMP, "grade_entry_id" INTEGER,
                FOREIGN KEY (lms_course_id) REFERENCES lms_courses(lms_course_id) ON DELETE CASCADE
            );
