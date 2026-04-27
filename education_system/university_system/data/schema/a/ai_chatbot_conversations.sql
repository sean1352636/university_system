CREATE TABLE IF NOT EXISTS ai_chatbot_conversations (
            conversation_id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT NOT NULL,
            user_type TEXT NOT NULL,
            start_time TEXT DEFAULT CURRENT_TIMESTAMP,
            end_time TEXT,
            message_count INTEGER DEFAULT 0,
            satisfaction_rating INTEGER,
            was_helpful BOOLEAN,
            escalated_to_human BOOLEAN DEFAULT 0
        );
