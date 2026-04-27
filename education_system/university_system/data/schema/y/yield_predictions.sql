CREATE TABLE IF NOT EXISTS yield_predictions (
            prediction_id INTEGER PRIMARY KEY AUTOINCREMENT,
            application_id INTEGER NOT NULL,
            predicted_enrollment_probability REAL,
            prediction_date TEXT DEFAULT CURRENT_TIMESTAMP,
            model_version TEXT,
            factors TEXT,
            FOREIGN KEY (application_id) REFERENCES admission_applications (application_id)
        );
