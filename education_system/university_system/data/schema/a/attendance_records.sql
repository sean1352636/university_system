CREATE TABLE IF NOT EXISTS attendance_records (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id TEXT,
            module_code TEXT,
            date TEXT,
            status TEXT,
            notes TEXT,
            recorded_by TEXT,
            recorded_at TEXT,
            check_in_method TEXT DEFAULT 'manual',
            location_data TEXT,
            ip_address TEXT,
            session_id TEXT,
            makeup_for_date TEXT,
            verification_status TEXT DEFAULT 'verified', "record_id" INTEGER, "latitude" REAL, "longitude" REAL, "device_id" TEXT, "facial_recognition_confidence" REAL, "check_in_time" TIMESTAMP DEFAULT NULL,
            FOREIGN KEY (student_id) REFERENCES students (student_id),
            FOREIGN KEY (module_code) REFERENCES modules (module_code)
        );
