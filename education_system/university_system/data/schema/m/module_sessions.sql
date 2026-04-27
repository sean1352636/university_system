CREATE TABLE IF NOT EXISTS module_sessions (
                       id INTEGER PRIMARY KEY AUTOINCREMENT,
                       module_code TEXT NOT NULL,
                       schedule_id INTEGER,
                       date TEXT NOT NULL,
                       start_time TEXT,
                       end_time TEXT,
                       generated_at TEXT DEFAULT (datetime('now')),
                       UNIQUE (module_code, date, start_time)
                   );
