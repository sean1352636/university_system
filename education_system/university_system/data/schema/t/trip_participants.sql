CREATE TABLE IF NOT EXISTS trip_participants (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                trip_id INTEGER NOT NULL,
                student_id TEXT,
                user_id INTEGER,
                registration_date TEXT NOT NULL,
                payment_status TEXT DEFAULT 'pending',
                emergency_contact TEXT,
                medical_info TEXT,
                dietary_requirements TEXT,
                status TEXT DEFAULT 'registered',
                FOREIGN KEY (trip_id) REFERENCES trips (id) ON DELETE CASCADE,
                FOREIGN KEY (student_id) REFERENCES students (student_id),
                FOREIGN KEY (user_id) REFERENCES users (id),
                UNIQUE (trip_id, student_id),
                CHECK (payment_status IN ('pending', 'partial', 'paid', 'refunded')),
                CHECK (status IN ('registered', 'waitlist', 'cancelled', 'attended'))
            );
