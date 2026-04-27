CREATE TABLE IF NOT EXISTS lms_access_grants (
         id INTEGER PRIMARY KEY AUTOINCREMENT,
         student_id TEXT NOT NULL, module_code TEXT NOT NULL,
         session_date TEXT NOT NULL, resource TEXT NOT NULL,
         granted INTEGER DEFAULT 0, reason TEXT,
         created_at TEXT DEFAULT CURRENT_TIMESTAMP,
         UNIQUE(student_id, module_code, session_date, resource)
       );
