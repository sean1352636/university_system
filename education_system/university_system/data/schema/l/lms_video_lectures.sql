CREATE TABLE IF NOT EXISTS lms_video_lectures (
                video_id INTEGER PRIMARY KEY AUTOINCREMENT,
                content_id INTEGER NOT NULL,
                video_url TEXT NOT NULL,
                duration_minutes INTEGER,
                thumbnail_url TEXT,
                transcript_url TEXT,
                video_quality TEXT DEFAULT '720p',
                view_count INTEGER DEFAULT 0,
                created_at TEXT NOT NULL DEFAULT (datetime('now')),
                FOREIGN KEY (content_id) REFERENCES lms_course_content(content_id) ON DELETE CASCADE
            );
