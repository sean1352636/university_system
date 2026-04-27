CREATE TABLE IF NOT EXISTS nailbar_appointment_treatments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                appointment_id INTEGER NOT NULL,
                treatment_id INTEGER NOT NULL,
                treatment_name TEXT NOT NULL,
                price DECIMAL(10,2) NOT NULL,
                duration_minutes INTEGER NOT NULL,
                notes TEXT,
                FOREIGN KEY (appointment_id) REFERENCES nailbar_appointments(appointment_id),
                FOREIGN KEY (treatment_id) REFERENCES nailbar_treatments(treatment_id)
            );
