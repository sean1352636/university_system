CREATE TABLE IF NOT EXISTS restaurant_shifts (
                shift_id INTEGER PRIMARY KEY AUTOINCREMENT,
                staff_id INTEGER NOT NULL,
                shift_date DATE NOT NULL,
                start_time TIME NOT NULL,
                end_time TIME,
                break_minutes INTEGER DEFAULT 0,
                hours_worked REAL,
                hourly_rate REAL,
                total_pay REAL,
                status TEXT DEFAULT 'Scheduled',
                notes TEXT,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (staff_id) REFERENCES restaurant_staff(staff_id)
            );
