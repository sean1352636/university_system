CREATE TABLE IF NOT EXISTS survey_responses (
            response_id INTEGER PRIMARY KEY AUTOINCREMENT,
            survey_id INTEGER,
            alumni_id TEXT,
            responses TEXT,
            submission_date TEXT,
            FOREIGN KEY (survey_id) REFERENCES event_surveys (survey_id),
            FOREIGN KEY (alumni_id) REFERENCES alumni (alumni_id)
        );
