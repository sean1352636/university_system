CREATE TABLE IF NOT EXISTS betting_events (
                    event_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    event_name TEXT NOT NULL,
                    event_type TEXT NOT NULL,
                    sport_type TEXT,
                    team_a TEXT,
                    team_b TEXT,
                    odds_a DECIMAL(6,2) DEFAULT 2.00,
                    odds_b DECIMAL(6,2) DEFAULT 2.00,
                    odds_draw DECIMAL(6,2),
                    event_date TEXT NOT NULL,
                    event_time TEXT,
                    status TEXT DEFAULT 'upcoming',
                    result TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    created_by TEXT
                );
