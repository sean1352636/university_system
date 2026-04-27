CREATE TABLE IF NOT EXISTS extracurricular_activities (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                activity_name TEXT,
                description TEXT,
                supervisor TEXT,
                meeting_schedule TEXT,
                location TEXT,
                max_participants INTEGER,
                fee DECIMAL(10,2) DEFAULT 0.00,
                status TEXT DEFAULT 'active'
            );
