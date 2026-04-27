CREATE TABLE IF NOT EXISTS poll_responses (
    response_id INTEGER PRIMARY KEY AUTOINCREMENT,
    poll_id INTEGER NOT NULL,
    user_id INTEGER NOT NULL,
    answer TEXT NOT NULL,
    is_correct BOOLEAN,
    response_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    time_taken INTEGER, "option_index" INTEGER, "responded_at" TIMESTAMP DEFAULT CURRENT_TIMESTAMP,  -- seconds
    FOREIGN KEY (poll_id) REFERENCES virtual_polls(poll_id) ON DELETE CASCADE,
    UNIQUE(poll_id, user_id)
);
