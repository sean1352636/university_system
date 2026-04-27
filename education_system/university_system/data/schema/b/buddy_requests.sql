CREATE TABLE IF NOT EXISTS buddy_requests (
                request_id INTEGER PRIMARY KEY AUTOINCREMENT,
                sender_id TEXT NOT NULL,
                receiver_id TEXT NOT NULL,
                request_type TEXT NOT NULL,
                destination TEXT,
                message TEXT,
                status TEXT DEFAULT 'pending',
                sent_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                responded_at TIMESTAMP,
                FOREIGN KEY (sender_id) REFERENCES users(username),
                FOREIGN KEY (receiver_id) REFERENCES users(username)
            );
