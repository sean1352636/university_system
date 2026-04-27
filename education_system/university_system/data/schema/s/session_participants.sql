CREATE TABLE IF NOT EXISTS session_participants (
    participant_id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id INTEGER NOT NULL,
    user_id INTEGER NOT NULL,
    user_type TEXT NOT NULL,  -- student, instructor, guest
    join_time TIMESTAMP,
    leave_time TIMESTAMP,
    duration INTEGER,  -- seconds
    connection_quality TEXT,  -- excellent, good, fair, poor
    device_type TEXT,  -- desktop, mobile, tablet
    is_muted BOOLEAN DEFAULT 0,
    is_video_on BOOLEAN DEFAULT 1,
    raised_hand_count INTEGER DEFAULT 0,
    chat_message_count INTEGER DEFAULT 0,
    attendance_status TEXT DEFAULT 'absent', "attendance_duration" INTEGER DEFAULT 0, "is_present" BOOLEAN DEFAULT 0, "joined_at" TIMESTAMP, "left_at" TIMESTAMP, "role" TEXT DEFAULT 'attendee',  -- present, absent, late, left_early
    FOREIGN KEY (session_id) REFERENCES virtual_sessions(session_id) ON DELETE CASCADE
);
