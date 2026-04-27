CREATE TABLE IF NOT EXISTS absence_requests (
                 id           INTEGER PRIMARY KEY AUTOINCREMENT,
                 student_id   TEXT NOT NULL,
                 module_code  TEXT NOT NULL,
                 date         TEXT NOT NULL,
                 reason       TEXT NOT NULL,
                 status       TEXT NOT NULL DEFAULT 'pending'
                              CHECK(status IN ('pending','approved','rejected')),
                 submitted_at TEXT DEFAULT CURRENT_TIMESTAMP
               );
