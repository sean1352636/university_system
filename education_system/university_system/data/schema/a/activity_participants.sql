CREATE TABLE IF NOT EXISTS activity_participants (
                participant_id INTEGER PRIMARY KEY AUTOINCREMENT,
                activity_id INTEGER NOT NULL,
                user_id TEXT NOT NULL,
                rsvp_status TEXT DEFAULT 'interested',
                joined_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (activity_id) REFERENCES social_activities(activity_id),
                FOREIGN KEY (user_id) REFERENCES users(username),
                UNIQUE(activity_id, user_id)
            );
