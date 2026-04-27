CREATE TABLE IF NOT EXISTS course_offerings (
                    offering_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    course_id TEXT NOT NULL,
                    offered_fall BOOLEAN DEFAULT 1,
                    offered_spring BOOLEAN DEFAULT 1,
                    offered_summer BOOLEAN DEFAULT 0,
                    offered_years TEXT DEFAULT 'Every',
                    typical_enrollment INTEGER DEFAULT 0,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (course_id) REFERENCES courses(course_id),
                    UNIQUE(course_id)
                );
