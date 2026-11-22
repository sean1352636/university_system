"""
Database schema for Virtual Classroom Integration
Scheduling and attendance records for sessions hosted on
Zoom / Teams / Meet. The meeting itself is not run here.
"""

VIRTUAL_CLASSROOM_SCHEMA = """
-- Virtual Classrooms
CREATE TABLE IF NOT EXISTS virtual_classrooms (
    classroom_id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_name TEXT NOT NULL,
    course_id TEXT,
    instructor_id INTEGER NOT NULL,
    platform TEXT NOT NULL,  -- 'zoom', 'teams', 'meet', 'webrtc'
    meeting_link TEXT,
    meeting_id TEXT,
    passcode TEXT,
    max_participants INTEGER DEFAULT 100,
    features TEXT,  -- JSON: {whiteboard, recording, screen_sharing}
    module_code TEXT,  -- module attendance is recorded against
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    is_active BOOLEAN DEFAULT 1,
    FOREIGN KEY (course_id) REFERENCES courses(id),
    FOREIGN KEY (instructor_id) REFERENCES instructors(id)
);

-- Virtual Sessions
CREATE TABLE IF NOT EXISTS virtual_sessions (
    session_id INTEGER PRIMARY KEY AUTOINCREMENT,
    classroom_id INTEGER NOT NULL,
    session_type TEXT DEFAULT 'lecture',  -- lecture, lab, office_hours, review
    start_time TIMESTAMP NOT NULL,
    end_time TIMESTAMP,
    actual_start_time TIMESTAMP,
    actual_end_time TIMESTAMP,
    recording_url TEXT,
    recording_size INTEGER,  -- bytes
    recording_duration INTEGER,  -- seconds
    status TEXT DEFAULT 'scheduled',  -- scheduled, in_progress, completed, cancelled
    notes TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (classroom_id) REFERENCES virtual_classrooms(classroom_id) ON DELETE CASCADE
);

-- Session Participants
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
    attendance_status TEXT DEFAULT 'absent',  -- present, absent, late, left_early
    FOREIGN KEY (session_id) REFERENCES virtual_sessions(session_id) ON DELETE CASCADE
);

-- Virtual Recordings
CREATE TABLE IF NOT EXISTS virtual_recordings (
    recording_id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id INTEGER NOT NULL,
    file_url TEXT NOT NULL,
    file_name TEXT,
    file_size INTEGER,  -- bytes
    duration INTEGER,  -- seconds
    format TEXT DEFAULT 'mp4',
    has_transcript BOOLEAN DEFAULT 0,
    transcript_url TEXT,
    has_captions BOOLEAN DEFAULT 0,
    captions_url TEXT,
    view_count INTEGER DEFAULT 0,
    download_count INTEGER DEFAULT 0,
    is_public BOOLEAN DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    expires_at TIMESTAMP,
    FOREIGN KEY (session_id) REFERENCES virtual_sessions(session_id) ON DELETE CASCADE
);





-- Create indexes for performance
CREATE INDEX IF NOT EXISTS idx_virtual_sessions_classroom
    ON virtual_sessions(classroom_id);
CREATE INDEX IF NOT EXISTS idx_virtual_sessions_start_time
    ON virtual_sessions(start_time);
CREATE INDEX IF NOT EXISTS idx_session_participants_session
    ON session_participants(session_id);
CREATE INDEX IF NOT EXISTS idx_session_participants_user
    ON session_participants(user_id);
CREATE INDEX IF NOT EXISTS idx_virtual_recordings_session
    ON virtual_recordings(session_id);
"""

def create_virtual_classroom_tables(conn):
    """Create all virtual classroom tables"""
    cursor = conn.cursor()
    cursor.executescript(VIRTUAL_CLASSROOM_SCHEMA)
    conn.commit()
    print("Virtual Classroom tables created successfully")

if __name__ == "__main__":
    from education_system.systems.university.infrastructure.database.db import sqlite3
    from education_system.paths import UNIVERSITY_DEFAULT_DB_PATH

    with sqlite3.connect(UNIVERSITY_DEFAULT_DB_PATH) as conn:
        create_virtual_classroom_tables(conn)
