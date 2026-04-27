CREATE TABLE IF NOT EXISTS alumni_achievements (
            achievement_id INTEGER PRIMARY KEY AUTOINCREMENT,
            alumni_id TEXT,
            achievement_title TEXT,
            achievement_description TEXT,
            achievement_date TEXT,
            category TEXT,
            verification_status TEXT DEFAULT 'pending',
            verified_by TEXT, "achievement_type" TEXT, "created_at" TEXT DEFAULT CURRENT_TIMESTAMP, "date_achieved" TEXT, "is_featured" BOOLEAN DEFAULT 0,
            FOREIGN KEY (alumni_id) REFERENCES alumni (alumni_id)
        );
