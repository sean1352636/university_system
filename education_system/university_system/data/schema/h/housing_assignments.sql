CREATE TABLE IF NOT EXISTS housing_assignments (
            assignment_id TEXT PRIMARY KEY,
            application_id TEXT,
            student_id TEXT NOT NULL,
            room_id TEXT NOT NULL,
            move_in_date TEXT NOT NULL,
            planned_move_out_date TEXT NOT NULL,
            actual_move_out_date TEXT,
            contract_number TEXT UNIQUE,
            monthly_rent REAL NOT NULL,
            status TEXT NOT NULL,
            assigned_by TEXT NOT NULL,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            FOREIGN KEY (application_id) REFERENCES housing_applications (application_id),
            FOREIGN KEY (student_id) REFERENCES students (student_id),
            FOREIGN KEY (room_id) REFERENCES housing_rooms (room_id)
        );
