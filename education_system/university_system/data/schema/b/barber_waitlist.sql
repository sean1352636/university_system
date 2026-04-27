CREATE TABLE IF NOT EXISTS barber_waitlist (
                waitlist_id INTEGER PRIMARY KEY AUTOINCREMENT,
                customer_id TEXT NOT NULL,
                customer_name TEXT NOT NULL,
                customer_email TEXT,
                customer_phone TEXT,
                preferred_date TEXT NOT NULL,
                preferred_time TEXT,
                service_id INTEGER,
                staff_id INTEGER,
                notes TEXT,
                status TEXT DEFAULT 'waiting',
                notification_sent_at TEXT,
                available_slot TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
