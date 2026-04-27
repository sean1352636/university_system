CREATE TABLE IF NOT EXISTS marketplace_messages (
                    message_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    listing_type TEXT NOT NULL,
                    listing_id INTEGER NOT NULL,
                    sender_id TEXT NOT NULL,
                    receiver_id TEXT NOT NULL,
                    message_text TEXT NOT NULL,
                    is_read BOOLEAN DEFAULT 0,
                    sent_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (sender_id) REFERENCES students(student_id),
                    FOREIGN KEY (receiver_id) REFERENCES students(student_id)
                );
