CREATE TABLE IF NOT EXISTS dentist_appointments (
                    appointment_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    appointment_ref TEXT UNIQUE NOT NULL,
                    patient_id INTEGER NOT NULL,
                    dentist_id TEXT NOT NULL,
                    dentist_name TEXT NOT NULL,
                    appointment_date DATE NOT NULL,
                    appointment_time TEXT NOT NULL,
                    duration_minutes INTEGER DEFAULT 30,
                    treatment_type TEXT NOT NULL,
                    status TEXT DEFAULT 'scheduled',
                    notes TEXT,
                    reminder_sent INTEGER DEFAULT 0,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    created_by TEXT,
                    FOREIGN KEY (patient_id) REFERENCES dentist_patients(patient_id)
                );
