CREATE TABLE IF NOT EXISTS student_biometrics (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id TEXT,
            face_encoding BLOB,
            face_photo_path TEXT,
            enrolled_date TEXT DEFAULT CURRENT_TIMESTAMP,
            last_updated TEXT DEFAULT CURRENT_TIMESTAMP,
            status TEXT DEFAULT 'active',
            FOREIGN KEY (student_id) REFERENCES students (student_id)
        );
