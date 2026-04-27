CREATE TABLE IF NOT EXISTS grant_tracker_alerts (
                id INTEGER PRIMARY KEY AUTOINCREMENT, grant_id INTEGER NOT NULL,
                alert_type TEXT DEFAULT 'submission', alert_date TEXT, message TEXT,
                is_sent INTEGER DEFAULT 0, sent_at TEXT,
                FOREIGN KEY (grant_id) REFERENCES grant_tracker_apps(id));
