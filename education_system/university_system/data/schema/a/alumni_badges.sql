CREATE TABLE IF NOT EXISTS alumni_badges (
            alumni_badge_id INTEGER PRIMARY KEY AUTOINCREMENT,
            alumni_id TEXT,
            badge_id INTEGER,
            earned_date TEXT,
            FOREIGN KEY (alumni_id) REFERENCES alumni (alumni_id),
            FOREIGN KEY (badge_id) REFERENCES achievement_badges (badge_id)
        );
