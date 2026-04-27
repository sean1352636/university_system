CREATE TABLE IF NOT EXISTS badge_progress (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    student_id TEXT NOT NULL,
                    badge_id INTEGER NOT NULL,
                    current_progress INTEGER DEFAULT 0,
                    target_progress INTEGER DEFAULT 100,
                    last_updated TEXT DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (badge_id) REFERENCES badge_definitions(id)
                );
