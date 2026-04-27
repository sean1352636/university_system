CREATE TABLE IF NOT EXISTS discovery_event_social_settings (
    user_id TEXT PRIMARY KEY,
    show_attendance_to_friends INTEGER DEFAULT 1,
    receive_friend_notifications INTEGER DEFAULT 1,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);
