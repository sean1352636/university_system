CREATE TABLE IF NOT EXISTS study_room_participants (
                    participant_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    room_id INTEGER NOT NULL,
                    student_id TEXT NOT NULL,
                    joined_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    left_at TEXT,
                    total_time_minutes INTEGER DEFAULT 0,
                    pomodoro_sessions_completed INTEGER DEFAULT 0,
                    is_currently_active BOOLEAN DEFAULT 1,
                    FOREIGN KEY (room_id) REFERENCES virtual_study_rooms(room_id) ON DELETE CASCADE
                );
