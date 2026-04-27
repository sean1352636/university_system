CREATE TABLE IF NOT EXISTS engagement_points (
            point_id INTEGER PRIMARY KEY AUTOINCREMENT,
            alumni_id TEXT,
            activity_type TEXT,
            points_earned INTEGER,
            activity_date TEXT,
            description TEXT,
            FOREIGN KEY (alumni_id) REFERENCES alumni (alumni_id)
        );
