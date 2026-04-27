CREATE TABLE IF NOT EXISTS abs_tracker_staff_prefs (
            user_id INTEGER, key TEXT, value TEXT,
            PRIMARY KEY (user_id, key)
        );
