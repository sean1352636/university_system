CREATE TABLE IF NOT EXISTS gym_attendance (
                    attendance_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    member_id INTEGER NOT NULL,
                    check_in TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    check_out TIMESTAMP,
                    FOREIGN KEY (member_id) REFERENCES gym_memberships(membership_id)
                );
