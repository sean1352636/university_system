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
    expires_at TIMESTAMP, "is_available" BOOLEAN DEFAULT 1, "recording_url" TEXT, "recorded_at" TIMESTAMP DEFAULT NULL,
    FOREIGN KEY (session_id) REFERENCES virtual_sessions(session_id) ON DELETE CASCADE
);
