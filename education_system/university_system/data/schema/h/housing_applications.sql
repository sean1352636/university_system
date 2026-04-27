CREATE TABLE IF NOT EXISTS housing_applications (
            application_id TEXT PRIMARY KEY,
            student_id TEXT NOT NULL,
            application_date TEXT NOT NULL,
            preferred_building_id TEXT,
            preferred_room_type TEXT NOT NULL,
            requested_move_in_date TEXT NOT NULL,
            requested_duration_months INTEGER NOT NULL,
            special_requirements TEXT,
            status TEXT NOT NULL,
            notes TEXT,
            reviewed_by TEXT,
            review_date TEXT,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            FOREIGN KEY (student_id) REFERENCES students (student_id),
            FOREIGN KEY (preferred_building_id) REFERENCES housing_buildings (building_id)
        );
