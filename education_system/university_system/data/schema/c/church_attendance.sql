CREATE TABLE IF NOT EXISTS church_attendance (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    service_date TEXT,
    service_type TEXT,
    attendance_count INTEGER,
    notes TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
