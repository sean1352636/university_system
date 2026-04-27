CREATE TABLE IF NOT EXISTS gym_class_bookings (
                    booking_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    booking_ref TEXT UNIQUE NOT NULL,
                    class_id INTEGER NOT NULL,
                    member_id INTEGER NOT NULL,
                    booking_date DATE NOT NULL,
                    status TEXT DEFAULT 'confirmed',
                    attended INTEGER DEFAULT 0,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (class_id) REFERENCES gym_classes(class_id),
                    FOREIGN KEY (member_id) REFERENCES gym_memberships(membership_id)
                );
