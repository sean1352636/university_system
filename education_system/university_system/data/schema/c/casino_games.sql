CREATE TABLE IF NOT EXISTS casino_games (
                    game_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id INTEGER,
                    user_id TEXT NOT NULL,
                    game_type TEXT NOT NULL,
                    bet_amount DECIMAL(10,2) NOT NULL,
                    result TEXT NOT NULL,
                    win_amount DECIMAL(10,2) DEFAULT 0.00,
                    game_data TEXT,
                    played_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (session_id) REFERENCES casino_sessions(session_id)
                );
