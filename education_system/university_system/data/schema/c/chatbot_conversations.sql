CREATE TABLE IF NOT EXISTS chatbot_conversations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            username TEXT NOT NULL,
            message TEXT NOT NULL,
            response TEXT NOT NULL,
            intent TEXT,
            confidence REAL,
            timestamp TEXT NOT NULL,
            session_id TEXT,
            FOREIGN KEY (user_id) REFERENCES users (id)
        );
