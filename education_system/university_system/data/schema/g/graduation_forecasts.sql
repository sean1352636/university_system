CREATE TABLE IF NOT EXISTS graduation_forecasts (
            forecast_id INTEGER PRIMARY KEY AUTOINCREMENT,
            cohort_year INTEGER NOT NULL,
            program_id INTEGER,
            predicted_graduation_rate REAL,
            predicted_4year_rate REAL,
            predicted_5year_rate REAL,
            predicted_6year_rate REAL,
            forecast_date TEXT DEFAULT CURRENT_TIMESTAMP,
            model_id INTEGER,
            confidence_interval TEXT,
            FOREIGN KEY (model_id) REFERENCES analytics_models (model_id)
        );
