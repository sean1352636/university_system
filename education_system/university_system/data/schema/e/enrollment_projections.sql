CREATE TABLE IF NOT EXISTS enrollment_projections (
            projection_id INTEGER PRIMARY KEY AUTOINCREMENT,
            academic_year TEXT NOT NULL,
            program_id INTEGER,
            projected_new_students INTEGER,
            projected_continuing_students INTEGER,
            projected_total_enrollment INTEGER,
            projection_date TEXT DEFAULT CURRENT_TIMESTAMP,
            model_id INTEGER,
            scenario TEXT,
            FOREIGN KEY (model_id) REFERENCES analytics_models (model_id)
        );
