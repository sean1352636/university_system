CREATE TABLE IF NOT EXISTS study_groups (
                    group_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    course_id TEXT NOT NULL,
                    group_name TEXT NOT NULL,
                    creator_id TEXT NOT NULL,
                    max_members INTEGER DEFAULT 6,
                    current_members INTEGER DEFAULT 1,
                    meeting_schedule TEXT,
                    location TEXT,
                    is_virtual BOOLEAN DEFAULT 1,
                    status TEXT DEFAULT 'Active',
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP
                , "description" TEXT, "meeting_time" TEXT, "organizer_id" TEXT, "study_date" TEXT, "study_group_id" INTEGER, "subject" TEXT, "topic" TEXT);
