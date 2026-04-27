CREATE TABLE IF NOT EXISTS barber_recurring_appointments (
                recurring_id INTEGER PRIMARY KEY AUTOINCREMENT,
                customer_id TEXT NOT NULL,
                customer_name TEXT NOT NULL,
                customer_email TEXT,
                service_id INTEGER NOT NULL,
                staff_id INTEGER,
                day_of_week INTEGER NOT NULL,
                appointment_time TEXT NOT NULL,
                frequency TEXT DEFAULT 'weekly',
                start_date TEXT NOT NULL,
                end_date TEXT,
                is_active INTEGER DEFAULT 1,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
