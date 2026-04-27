CREATE TABLE IF NOT EXISTS virtual_study_rooms (
                    room_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    group_id INTEGER,
                    room_name TEXT NOT NULL,
                    room_code TEXT NOT NULL UNIQUE,
                    host_id TEXT NOT NULL,
                    course_id TEXT,
                    max_participants INTEGER DEFAULT 8,
                    current_participants INTEGER DEFAULT 0,
                    pomodoro_enabled BOOLEAN DEFAULT 1,
                    work_duration INTEGER DEFAULT 25,
                    break_duration INTEGER DEFAULT 5,
                    session_count INTEGER DEFAULT 0,
                    is_active BOOLEAN DEFAULT 1,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    ended_at TEXT,
                    FOREIGN KEY (group_id) REFERENCES study_groups(group_id)
                );
