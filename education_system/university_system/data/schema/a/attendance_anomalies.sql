CREATE TABLE IF NOT EXISTS attendance_anomalies (
         id INTEGER PRIMARY KEY AUTOINCREMENT,
         kind TEXT NOT NULL,
         student_id TEXT, module_code TEXT, details TEXT,
         severity TEXT DEFAULT 'medium',
         detected_at TEXT DEFAULT CURRENT_TIMESTAMP,
         resolved INTEGER DEFAULT 0
       );
