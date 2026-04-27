CREATE TABLE IF NOT EXISTS sports_bets (
                    bet_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id TEXT NOT NULL,
                    event_id INTEGER NOT NULL,
                    bet_type TEXT NOT NULL,
                    selection TEXT NOT NULL,
                    odds DECIMAL(6,2) NOT NULL,
                    stake DECIMAL(10,2) NOT NULL,
                    potential_return DECIMAL(10,2) NOT NULL,
                    actual_return DECIMAL(10,2) DEFAULT 0.00,
                    status TEXT DEFAULT 'pending',
                    placed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    settled_at TIMESTAMP,
                    FOREIGN KEY (event_id) REFERENCES betting_events(event_id)
                );
