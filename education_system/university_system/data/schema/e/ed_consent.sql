CREATE TABLE IF NOT EXISTS ed_consent (
        person_id INTEGER PRIMARY KEY,
        consent_flags TEXT NOT NULL,
        updated_at TEXT NOT NULL,
        FOREIGN KEY (person_id) REFERENCES ed_people(id) ON DELETE CASCADE
    );
