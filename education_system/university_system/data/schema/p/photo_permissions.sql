CREATE TABLE IF NOT EXISTS photo_permissions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                student_id TEXT,
                permission_type TEXT,
                consent_given BOOLEAN DEFAULT 0,
                conditions TEXT,
                valid_from TEXT,
                valid_until TEXT,
                parent_signature TEXT,
                date_signed TEXT,
                FOREIGN KEY (student_id) REFERENCES students (student_id)
            );
