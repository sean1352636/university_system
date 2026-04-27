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
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP, "actual_end" TIMESTAMP, "actual_start" TIMESTAMP, "host_id" INTEGER, "max_duration" INTEGER DEFAULT 120, "meeting_link" TEXT, "recording_enabled" BOOLEAN DEFAULT 0, "scheduled_end" TIMESTAMP, "scheduled_start" TIMESTAMP, "session_title" TEXT,
    FOREIGN KEY (classroom_id) REFERENCES virtual_classrooms(classroom_id) ON DELETE CASCADE
);
