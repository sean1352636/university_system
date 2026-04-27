CREATE TABLE IF NOT EXISTS virtual_chat_messages (
    message_id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id INTEGER NOT NULL,
    user_id INTEGER NOT NULL,
    user_name TEXT NOT NULL,
    message_text TEXT NOT NULL,
    message_type TEXT DEFAULT 'public',  -- public, private, announcement
    recipient_id INTEGER,  -- for private messages
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    is_deleted BOOLEAN DEFAULT 0,
    replied_to INTEGER,  -- message_id of parent message
    reactions TEXT, "is_private" BOOLEAN DEFAULT 0, "sent_at" TIMESTAMP DEFAULT CURRENT_TIMESTAMP,  -- JSON: {emoji: count}
    FOREIGN KEY (session_id) REFERENCES virtual_sessions(session_id) ON DELETE CASCADE,
    FOREIGN KEY (replied_to) REFERENCES virtual_chat_messages(message_id)
);
