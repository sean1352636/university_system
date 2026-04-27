CREATE TABLE IF NOT EXISTS message_recipients (
    recipient_id INTEGER PRIMARY KEY AUTOINCREMENT,
    message_id INTEGER NOT NULL,
    user_id INTEGER NOT NULL,
    delivery_status TEXT DEFAULT 'pending',  -- pending, sent, delivered, failed, read
    delivered_at TIMESTAMP,
    read_at TIMESTAMP,
    error_message TEXT,
    FOREIGN KEY (message_id) REFERENCES messages(message_id) ON DELETE CASCADE
);
