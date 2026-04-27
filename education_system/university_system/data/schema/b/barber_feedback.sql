CREATE TABLE IF NOT EXISTS barber_feedback (
                feedback_id INTEGER PRIMARY KEY AUTOINCREMENT,
                appointment_id INTEGER,
                customer_id TEXT NOT NULL,
                staff_id INTEGER,
                rating INTEGER NOT NULL,
                comment TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (appointment_id) REFERENCES barber_appointments(appointment_id)
            );
