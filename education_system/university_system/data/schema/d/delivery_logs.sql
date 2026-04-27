CREATE TABLE IF NOT EXISTS delivery_logs (
    log_id INTEGER PRIMARY KEY AUTOINCREMENT,
    message_id INTEGER,
    recipient_id INTEGER,
    delivery_method TEXT NOT NULL,  -- email, sms, push
    delivery_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    status TEXT NOT NULL,  -- success, failed, bounced
    error_message TEXT,
    response_code TEXT,
    provider_message_id TEXT,
    FOREIGN KEY (message_id) REFERENCES messages(message_id)
);
