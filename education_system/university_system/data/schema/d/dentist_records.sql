CREATE TABLE IF NOT EXISTS dentist_records (
                    record_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    patient_id INTEGER NOT NULL,
                    record_type TEXT NOT NULL,
                    record_date DATE NOT NULL,
                    description TEXT,
                    file_path TEXT,
                    created_by TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (patient_id) REFERENCES dentist_patients(patient_id)
                );
