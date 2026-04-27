CREATE TABLE IF NOT EXISTS lms_discussion_forums (
                forum_id INTEGER PRIMARY KEY AUTOINCREMENT,
                lms_course_id INTEGER NOT NULL,
                topic TEXT NOT NULL,
                description TEXT,
                created_by TEXT NOT NULL,
                is_pinned INTEGER DEFAULT 0,
                is_locked INTEGER DEFAULT 0,
                created_at TEXT NOT NULL DEFAULT (datetime('now')), "updated_at" TIMESTAMP DEFAULT NULL,
                FOREIGN KEY (lms_course_id) REFERENCES lms_courses(lms_course_id) ON DELETE CASCADE
            );
