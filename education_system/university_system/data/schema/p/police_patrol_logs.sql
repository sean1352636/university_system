CREATE TABLE IF NOT EXISTS police_patrol_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    officer TEXT,
    area TEXT,
    start_time TEXT,
    end_time TEXT,
    status TEXT,
    notes TEXT,
    date TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
