CREATE TABLE IF NOT EXISTS barber_reminders (
                reminder_id INTEGER PRIMARY KEY AUTOINCREMENT,
                appointment_id INTEGER NOT NULL,
                reminder_type TEXT NOT NULL,
                scheduled_for TEXT NOT NULL,
                channel TEXT DEFAULT 'email',
                is_sent INTEGER DEFAULT 0,
                sent_at TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (appointment_id) REFERENCES barber_appointments(appointment_id)
            );
