CREATE TABLE IF NOT EXISTS breakout_rooms (
    room_id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id INTEGER NOT NULL,
    room_name TEXT NOT NULL,
    room_number INTEGER,
    participants TEXT,  -- JSON array of user_ids
    facilitator_id INTEGER,
    max_capacity INTEGER DEFAULT 10,
    topic TEXT,
    start_time TIMESTAMP,
    end_time TIMESTAMP,
    duration INTEGER,  -- minutes
    is_active BOOLEAN DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (session_id) REFERENCES virtual_sessions(session_id) ON DELETE CASCADE
);
