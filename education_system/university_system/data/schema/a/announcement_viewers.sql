CREATE TABLE IF NOT EXISTS announcement_viewers (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                announcement_id INTEGER NOT NULL,
                viewer_id INTEGER NOT NULL,
                viewed_at TEXT NOT NULL,
                FOREIGN KEY (announcement_id) REFERENCES announcements (id),
                FOREIGN KEY (viewer_id) REFERENCES users (id)
            );
