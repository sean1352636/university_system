CREATE TABLE IF NOT EXISTS frequent_absence_email_prefs (
                       student_id  TEXT PRIMARY KEY,
                       opted_out   INTEGER NOT NULL DEFAULT 0,
                       updated_at  TEXT
                   );
