CREATE TABLE IF NOT EXISTS competition_participants (
            participant_id INTEGER PRIMARY KEY AUTOINCREMENT,
            competition_id INTEGER,
            club_id INTEGER,
            student_id TEXT,
            registration_date TEXT,
            score REAL DEFAULT 0.0,
            rank_position INTEGER,
            FOREIGN KEY (competition_id) REFERENCES club_competitions (competition_id),
            FOREIGN KEY (club_id) REFERENCES student_clubs (club_id),
            FOREIGN KEY (student_id) REFERENCES students (student_id)
        );
