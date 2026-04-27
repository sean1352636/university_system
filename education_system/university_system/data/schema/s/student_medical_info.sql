CREATE TABLE IF NOT EXISTS student_medical_info (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                student_id TEXT,
                condition_type TEXT,
                description TEXT,
                medication_name TEXT,
                dosage TEXT,
                administration_time TEXT,
                emergency_contact TEXT,
                doctor_contact TEXT,
                expiry_date TEXT,
                notes TEXT,
                FOREIGN KEY (student_id) REFERENCES students (student_id)
            );
