CREATE TABLE IF NOT EXISTS peer_tutoring_requests (
                request_id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id INTEGER,
                student_id TEXT NOT NULL,
                message TEXT,
                status TEXT DEFAULT 'pending',
                created_at TEXT,
                FOREIGN KEY (session_id) REFERENCES peer_tutoring_sessions (session_id)
            );
