CREATE TABLE IF NOT EXISTS medical_info (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    student_id TEXT NOT NULL,
                    blood_type TEXT,
                    allergies TEXT,
                    medications TEXT,
                    conditions TEXT,
                    doctor_name TEXT,
                    doctor_phone TEXT,
                    insurance_provider TEXT,
                    insurance_policy TEXT,
                    last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
