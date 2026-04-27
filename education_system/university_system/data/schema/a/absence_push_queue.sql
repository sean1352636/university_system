CREATE TABLE IF NOT EXISTS absence_push_queue (
         id INTEGER PRIMARY KEY AUTOINCREMENT,
         user_id TEXT NOT NULL,
         title TEXT NOT NULL, body TEXT NOT NULL, payload TEXT,
         created_at TEXT DEFAULT CURRENT_TIMESTAMP,
         delivered_at TEXT, status TEXT DEFAULT 'pending'
       );
