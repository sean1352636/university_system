CREATE TABLE IF NOT EXISTS attendance_kiosks (
         kiosk_id TEXT PRIMARY KEY,
         room TEXT, lat REAL, lon REAL,
         radius_m REAL DEFAULT 50,
         active INTEGER DEFAULT 1
       );
