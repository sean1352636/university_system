CREATE TABLE IF NOT EXISTS virtual_classrooms (
    classroom_id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_name TEXT NOT NULL,
    course_id INTEGER,
    instructor_id INTEGER NOT NULL,
    platform TEXT NOT NULL,  -- 'zoom', 'teams', 'meet', 'webrtc'
    meeting_link TEXT,
    meeting_id TEXT,
    passcode TEXT,
    max_participants INTEGER DEFAULT 100,
    features TEXT,  -- JSON: {whiteboard, breakout_rooms, recording, polling}
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    is_active BOOLEAN DEFAULT 1, "access_code" TEXT, "classroom_name" TEXT, "meeting_url" TEXT,
    FOREIGN KEY (course_id) REFERENCES courses(course_id),
    FOREIGN KEY (instructor_id) REFERENCES instructors(instructor_id)
);
