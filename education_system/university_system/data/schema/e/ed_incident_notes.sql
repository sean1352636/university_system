CREATE TABLE IF NOT EXISTS ed_incident_notes (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        incident_id INTEGER NOT NULL,
        author TEXT NOT NULL,
        ts TEXT NOT NULL,
        note_type TEXT,
        body TEXT NOT NULL,
        FOREIGN KEY (incident_id) REFERENCES ed_incidents(id) ON DELETE CASCADE
    );
