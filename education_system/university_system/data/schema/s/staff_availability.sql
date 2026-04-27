CREATE TABLE IF NOT EXISTS staff_availability (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            staff_id INTEGER NOT NULL,
            day_of_week INTEGER NOT NULL,
            available_from TEXT,
            available_until TEXT,
            is_available INTEGER DEFAULT 1,
            notes TEXT,
            FOREIGN KEY (staff_id) REFERENCES staff(id),
            UNIQUE(staff_id, day_of_week)
        );
