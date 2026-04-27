CREATE TABLE IF NOT EXISTS grant_tracker_milestones (
                id INTEGER PRIMARY KEY AUTOINCREMENT, grant_id INTEGER NOT NULL,
                milestone_title TEXT NOT NULL, description TEXT, deadline TEXT,
                status TEXT DEFAULT 'pending', completed_at TEXT, notes TEXT,
                FOREIGN KEY (grant_id) REFERENCES grant_tracker_apps(id));
