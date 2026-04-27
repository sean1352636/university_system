CREATE TABLE IF NOT EXISTS pickup_authorizations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                student_id TEXT,
                authorized_person_name TEXT,
                relationship TEXT,
                phone_number TEXT,
                id_number TEXT,
                photo_path TEXT,
                valid_from TEXT,
                valid_until TEXT,
                active BOOLEAN DEFAULT 1,
                created_by TEXT,
                FOREIGN KEY (student_id) REFERENCES students (student_id)
            );
