CREATE TABLE IF NOT EXISTS navigation_history (
                    history_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id TEXT,
                    start_location TEXT NOT NULL,
                    end_location TEXT NOT NULL,
                    route_taken TEXT,
                    duration_minutes INTEGER,
                    accessibility_required BOOLEAN DEFAULT 0,
                    navigation_date TEXT DEFAULT CURRENT_TIMESTAMP,
                    rating INTEGER,
                    feedback TEXT
                );
