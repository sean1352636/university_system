CREATE TABLE IF NOT EXISTS restaurant_shift_swaps (
                swap_id INTEGER PRIMARY KEY AUTOINCREMENT,
                original_shift_id INTEGER NOT NULL,
                requesting_staff_id INTEGER NOT NULL,
                covering_staff_id INTEGER,
                swap_date DATE NOT NULL,
                status TEXT DEFAULT 'Pending',
                notes TEXT,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (original_shift_id) REFERENCES restaurant_shifts(shift_id),
                FOREIGN KEY (requesting_staff_id) REFERENCES restaurant_staff(staff_id),
                FOREIGN KEY (covering_staff_id) REFERENCES restaurant_staff(staff_id)
            );
