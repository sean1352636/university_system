CREATE TABLE IF NOT EXISTS lms_course_content (
                content_id INTEGER PRIMARY KEY AUTOINCREMENT,
                lms_course_id INTEGER NOT NULL,
                content_type TEXT NOT NULL,
                title TEXT NOT NULL,
                description TEXT,
                content_url TEXT,
                content_order INTEGER DEFAULT 0,
                release_date TEXT,
                is_published INTEGER DEFAULT 1,
                created_at TEXT NOT NULL DEFAULT (datetime('now')), "updated_at" TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (lms_course_id) REFERENCES lms_courses(lms_course_id) ON DELETE CASCADE
            );
