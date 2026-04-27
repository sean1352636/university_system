CREATE TABLE IF NOT EXISTS achievement_badges (
            badge_id INTEGER PRIMARY KEY AUTOINCREMENT,
            badge_name TEXT,
            badge_description TEXT,
            points_required INTEGER,
            badge_icon TEXT,
            category TEXT
        );
