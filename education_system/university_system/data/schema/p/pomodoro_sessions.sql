CREATE TABLE IF NOT EXISTS pomodoro_sessions (
                    session_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    room_id INTEGER NOT NULL,
                    student_id TEXT NOT NULL,
                    session_type TEXT NOT NULL,
                    start_time TEXT NOT NULL,
                    end_time TEXT,
                    duration_minutes INTEGER,
                    completed BOOLEAN DEFAULT 0,
                    FOREIGN KEY (room_id) REFERENCES virtual_study_rooms(room_id) ON DELETE CASCADE
                );
