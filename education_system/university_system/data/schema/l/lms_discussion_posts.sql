CREATE TABLE IF NOT EXISTS lms_discussion_posts (
                post_id INTEGER PRIMARY KEY AUTOINCREMENT,
                forum_id INTEGER NOT NULL,
                user_id TEXT NOT NULL,
                content TEXT NOT NULL,
                parent_post_id INTEGER,
                attachments TEXT,
                likes_count INTEGER DEFAULT 0,
                is_instructor_post INTEGER DEFAULT 0,
                created_at TEXT NOT NULL DEFAULT (datetime('now')), "updated_at" TIMESTAMP DEFAULT NULL,
                FOREIGN KEY (forum_id) REFERENCES lms_discussion_forums(forum_id) ON DELETE CASCADE,
                FOREIGN KEY (parent_post_id) REFERENCES lms_discussion_posts(post_id) ON DELETE CASCADE
            );
