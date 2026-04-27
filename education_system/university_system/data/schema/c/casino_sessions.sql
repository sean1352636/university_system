CREATE TABLE IF NOT EXISTS casino_sessions (
                    session_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id TEXT NOT NULL,
                    game_type TEXT NOT NULL,
                    start_balance DECIMAL(10,2) NOT NULL,
                    end_balance DECIMAL(10,2),
                    total_wagered DECIMAL(10,2) DEFAULT 0.00,
                    total_won DECIMAL(10,2) DEFAULT 0.00,
                    hands_played INTEGER DEFAULT 0,
                    started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    ended_at TIMESTAMP,
                    status TEXT DEFAULT 'active'
                );
