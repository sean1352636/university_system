CREATE TABLE IF NOT EXISTS notification_subscriptions (
    subscription_id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    topic TEXT NOT NULL,  -- course_updates, events, grades, announcements
    channel TEXT DEFAULT 'email',  -- email, sms, push
    is_active BOOLEAN DEFAULT 1,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(user_id),
    UNIQUE(user_id, topic, channel)
);
