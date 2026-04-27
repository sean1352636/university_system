CREATE TABLE IF NOT EXISTS course_demand_predictions (
            prediction_id INTEGER PRIMARY KEY AUTOINCREMENT,
            module_code TEXT NOT NULL,
            academic_year TEXT NOT NULL,
            semester TEXT NOT NULL,
            predicted_enrollment INTEGER,
            actual_enrollment INTEGER,
            prediction_date TEXT DEFAULT CURRENT_TIMESTAMP,
            model_id INTEGER,
            factors TEXT,
            FOREIGN KEY (module_code) REFERENCES modules (module_code),
            FOREIGN KEY (model_id) REFERENCES analytics_models (model_id)
        );
