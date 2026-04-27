CREATE TABLE IF NOT EXISTS gym_pt_sessions (
                    session_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    booking_ref TEXT UNIQUE NOT NULL,
                    member_id INTEGER NOT NULL,
                    trainer_id TEXT,
                    trainer_name TEXT NOT NULL,
                    session_date DATE NOT NULL,
                    session_time TEXT NOT NULL,
                    duration_minutes INTEGER DEFAULT 60,
                    session_type TEXT DEFAULT 'single',
                    fee DECIMAL(10,2) NOT NULL,
                    payment_status TEXT DEFAULT 'pending',
                    status TEXT DEFAULT 'scheduled',
                    notes TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (member_id) REFERENCES gym_memberships(membership_id)
                );
