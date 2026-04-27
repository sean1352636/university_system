CREATE TABLE IF NOT EXISTS prediction_bets (
                    bet_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id TEXT NOT NULL,
                    market_id INTEGER NOT NULL,
                    selection TEXT NOT NULL,
                    stake DECIMAL(10,2) NOT NULL,
                    odds_at_placement DECIMAL(6,2) NOT NULL,
                    potential_return DECIMAL(10,2) NOT NULL,
                    actual_return DECIMAL(10,2) DEFAULT 0.00,
                    status TEXT DEFAULT 'pending',
                    placed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    settled_at TIMESTAMP,
                    FOREIGN KEY (market_id) REFERENCES prediction_markets(market_id)
                );
