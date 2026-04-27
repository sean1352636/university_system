CREATE TABLE IF NOT EXISTS grievance_meetings (
                    meeting_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    grievance_id INTEGER NOT NULL,
                    meeting_date TEXT NOT NULL,
                    meeting_time TEXT,
                    location TEXT,
                    attendees TEXT,
                    purpose TEXT,
                    minutes TEXT,
                    outcomes TEXT,
                    follow_up_actions TEXT,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (grievance_id) REFERENCES grievances(grievance_id)
                );
