CREATE TABLE IF NOT EXISTS exam_accommodations (
    accommodation_id INTEGER PRIMARY KEY AUTOINCREMENT,
    student_id INTEGER NOT NULL,
    exam_id INTEGER,
    extended_time INTEGER,  -- minutes
    separate_room BOOLEAN DEFAULT 0,
    assistive_technology TEXT,
    reader_scribe BOOLEAN DEFAULT 0,
    status TEXT DEFAULT 'active', notes TEXT, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (student_id) REFERENCES students(student_id)
);
