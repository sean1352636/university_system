CREATE TABLE IF NOT EXISTS trip_staff (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                trip_id INTEGER NOT NULL,
                staff_user_id INTEGER NOT NULL,
                role TEXT DEFAULT 'supervisor',
                assigned_date TEXT NOT NULL,
                FOREIGN KEY (trip_id) REFERENCES trips (id) ON DELETE CASCADE,
                FOREIGN KEY (staff_user_id) REFERENCES users (id),
                UNIQUE (trip_id, staff_user_id),
                CHECK (role IN ('supervisor', 'coordinator', 'medical', 'transport'))
            );
