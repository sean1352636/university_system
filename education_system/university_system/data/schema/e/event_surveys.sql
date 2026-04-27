CREATE TABLE IF NOT EXISTS event_surveys (
            survey_id INTEGER PRIMARY KEY AUTOINCREMENT,
            event_id INTEGER,
            survey_title TEXT,
            questions TEXT,
            created_date TEXT,
            FOREIGN KEY (event_id) REFERENCES alumni_events (event_id)
        );
